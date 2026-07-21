#!/usr/bin/env bash
set -euo pipefail

# The build has two sources of runtime payloads: maintained source for the active
# game series and checksum-frozen recovered files for older series. Keeping that
# split explicit prevents a current build from silently rewriting shipped history.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rimworld_input="${RIMWORLD_DIR:-${HOME:?HOME must be set}/.steam/steam/steamapps/common/RimWorld}"
project="$repo_root/Source/VoidShelf/VoidShelf.csproj"
metadata="$repo_root/About/About.xml"
built_dll="$repo_root/Source/VoidShelf/bin/Release/net472/VoidShelf.dll"
active_version="1.6"
frozen_versions=("1.5")
declare -A frozen_defs_sha256=(["1.5"]="cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca")
declare -A frozen_dll_sha256=(["1.5"]="67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20")

# Metadata is the package and release identity shared by every tool. Source
# validation runs before artifact cleanup so malformed inputs cannot destroy the
# last usable local package.
python3 "$repo_root/scripts/validate-source.py" "$repo_root"
package_name="$(python3 "$repo_root/scripts/project.py" "$metadata" package-name)"
mod_version="$(python3 "$repo_root/scripts/project.py" "$metadata" version)"
supported_versions="$(python3 "$repo_root/scripts/project.py" "$metadata" supported-versions)"
if [[ "$supported_versions" != "1.5 1.6" ]]; then
    printf 'Error: Void Shelf build supports exactly RimWorld 1.5 and 1.6, found: %s\n' "$supported_versions" >&2
    exit 1
fi
mkdir -p -- "$repo_root/artifacts"
if [[ -n "${ARTIFACT_LOCK_FD:-}" ]]; then
    if [[ ! "$ARTIFACT_LOCK_FD" =~ ^[0-9]+$ || ! -e "/proc/$$/fd/$ARTIFACT_LOCK_FD" ]]; then
        printf 'Error: ARTIFACT_LOCK_FD must name an inherited open descriptor.\n' >&2
        exit 1
    fi
    lock_target="$(realpath -e -- "/proc/$$/fd/$ARTIFACT_LOCK_FD")"
    if [[ "$lock_target" != "$(realpath -e -- "$repo_root/artifacts")" ]]; then
        printf 'Error: ARTIFACT_LOCK_FD does not protect the artifacts directory.\n' >&2
        exit 1
    fi
    flock "$ARTIFACT_LOCK_FD"
else
    exec 8<"$repo_root/artifacts"
    flock 8
fi
artifact_dir="$repo_root/artifacts/$package_name"

# Canonical paths make later existence checks operate on the actual installation
# rather than an unresolved or missing path.
canonical_dir() {
    if [[ ! -d "$1" ]]; then
        printf 'Error: required directory does not exist: %s\n' "$1" >&2
        exit 1
    fi
    realpath -e -- "$1"
}

rimworld_dir="$(canonical_dir "$rimworld_input")"
managed_dir="$(canonical_dir "$rimworld_dir/RimWorldLinux_Data/Managed")"
version_file="$rimworld_dir/Version.txt"

# Compile only against the game series represented by the maintained Defs. An
# accidental cross-version compile can succeed while producing a broken mod.
if [[ ! -f "$version_file" ]]; then
    printf 'Error: RimWorld Version.txt is missing: %s\n' "$version_file" >&2
    exit 1
fi
version_text="$(<"$version_file")"
if [[ "$version_text" =~ ^([0-9]+)\.([0-9]+)(\.[0-9]+)?([[:space:]].*)?$ ]]; then
    installed_version="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
else
    printf 'Error: could not determine RimWorld major.minor from: %s\n' "$version_file" >&2
    exit 1
fi
if [[ "$installed_version" != "$active_version" ]]; then
    printf 'Error: installed RimWorld %s does not match active build version %s.\n' "$installed_version" "$active_version" >&2
    exit 1
fi
if [[ ! -f "$project" || ! -f "$managed_dir/Assembly-CSharp.dll" || ! -d "$repo_root/$active_version/Defs" ]]; then
    printf 'Error: project, Assembly-CSharp.dll, or active Defs are missing.\n' >&2
    exit 1
fi

# Frozen payload hashes are release-integrity contracts. Old Defs and binaries
# are copied verbatim; changing one requires an intentional version rollover.
for frozen_version in "${frozen_versions[@]}"; do
    if [[ "$frozen_version" == "$active_version" ]]; then
        printf 'Error: frozen version overlaps active version: %s\n' "$frozen_version" >&2
        exit 1
    fi
    frozen_defs="$repo_root/$frozen_version/Defs/Buildings.xml"
    frozen_dll="$repo_root/$frozen_version/Assemblies/VoidShelf.dll"
    if [[ ! -f "$frozen_defs" || ! -f "$frozen_dll" ]]; then
        printf 'Error: frozen %s Defs or DLL is missing.\n' "$frozen_version" >&2
        exit 1
    fi
    actual_defs_sha256="$(sha256sum -- "$frozen_defs")"
    actual_defs_sha256="${actual_defs_sha256%% *}"
    actual_dll_sha256="$(sha256sum -- "$frozen_dll")"
    actual_dll_sha256="${actual_dll_sha256%% *}"
    if [[ "$actual_defs_sha256" != "${frozen_defs_sha256[$frozen_version]}" || "$actual_dll_sha256" != "${frozen_dll_sha256[$frozen_version]}" ]]; then
        printf 'Error: frozen %s payload hash mismatch.\n' "$frozen_version" >&2
        exit 1
    fi
done

# Remove ignored intermediates before restore so stale outputs cannot satisfy an
# incremental build from a different source revision. Release compilation omits
# persistent compiler and debug metadata through the project contract.
printf 'Repository: %s\nVersion: %s\nRimWorld: %s\nManaged DLLs: %s\n' "$repo_root" "$mod_version" "$rimworld_dir" "$managed_dir"
rm -rf -- "$repo_root/Source/VoidShelf/bin" "$repo_root/Source/VoidShelf/obj"
dotnet restore "$project" --locked-mode
dotnet build "$project" --configuration Release --no-restore --no-incremental -p:ModVersion="$mod_version" -p:RimWorldManagedDir="$managed_dir"

if [[ ! -f "$built_dll" ]]; then
    printf 'Error: build output is missing: %s\n' "$built_dll" >&2
    exit 1
fi

# Assemble and validate a private sibling before replacing the last known-good
# package. The artifact lock serializes this final swap with releases and installs.
package_stage_root="$(mktemp -d -- "$repo_root/artifacts/.$package_name.package.XXXXXX")"
package_stage="$package_stage_root/$package_name"
package_backup=""
package_committed=false
cleanup_package() {
    local status=$?
    trap - EXIT
    set +e
    [[ -d "$package_stage_root" ]] && rm -rf -- "$package_stage_root"
    if [[ "$package_committed" != true && -n "$package_backup" && -e "$package_backup" && ! -e "$artifact_dir" ]]; then
        mv -T -- "$package_backup" "$artifact_dir"
    fi
    exit "$status"
}
trap cleanup_package EXIT
mkdir -p -- "$package_stage/$active_version/Assemblies"
cp -a -- "$repo_root/About" "$package_stage/"
cp -- "$repo_root/LoadFolders.xml" "$package_stage/LoadFolders.xml"
cp -- "$repo_root/LICENSE" "$package_stage/LICENSE"
for frozen_version in "${frozen_versions[@]}"; do
    cp -a -- "$repo_root/$frozen_version" "$package_stage/"
done
cp -a -- "$repo_root/$active_version/Defs" "$package_stage/$active_version/"
cp -- "$built_dll" "$package_stage/$active_version/Assemblies/VoidShelf.dll"

# Validate the assembled tree rather than trusting the copy operations alone.
python3 "$repo_root/scripts/validate-package.py" "$package_stage" --rimworld-dir "$rimworld_dir"
if [[ -e "$artifact_dir" || -L "$artifact_dir" ]]; then
    package_backup="$(mktemp -d -- "$repo_root/artifacts/.$package_name.previous.XXXXXX")"
    rmdir -- "$package_backup"
    mv -T -- "$artifact_dir" "$package_backup"
fi
mv -T -- "$package_stage" "$artifact_dir"
rmdir -- "$package_stage_root"
package_committed=true
trap - EXIT
if [[ -n "$package_backup" ]] && ! rm -rf -- "$package_backup"; then
    printf 'Warning: retained previous package backup at %s\n' "$package_backup" >&2
fi
printf 'Success: packaged Void Shelf %s at %s\n' "$mod_version" "$artifact_dir"
