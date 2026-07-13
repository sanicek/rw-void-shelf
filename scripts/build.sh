#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rimworld_input="${RIMWORLD_DIR:-${HOME:?HOME must be set}/.steam/steam/steamapps/common/RimWorld}"
project="$repo_root/Source/VoidShelf/VoidShelf.csproj"
artifact_dir="$repo_root/artifacts/VoidShelf"
built_dll="$repo_root/Source/VoidShelf/bin/Release/net472/VoidShelf.dll"
active_version="1.6"
frozen_versions=("1.5")
declare -A frozen_defs_sha256=(["1.5"]="cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca")
declare -A frozen_dll_sha256=(["1.5"]="67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20")

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

printf 'Repository: %s\nRimWorld: %s\nManaged DLLs: %s\n' "$repo_root" "$rimworld_dir" "$managed_dir"
dotnet restore "$project" --locked-mode
dotnet build "$project" --configuration Release --no-restore -p:RimWorldManagedDir="$managed_dir"

if [[ ! -f "$built_dll" ]]; then
    printf 'Error: build output is missing: %s\n' "$built_dll" >&2
    exit 1
fi
rm -rf -- "$artifact_dir"
mkdir -p -- "$artifact_dir/$active_version/Assemblies"
cp -a -- "$repo_root/About" "$artifact_dir/"
cp -- "$repo_root/LoadFolders.xml" "$artifact_dir/LoadFolders.xml"
for frozen_version in "${frozen_versions[@]}"; do
    cp -a -- "$repo_root/$frozen_version" "$artifact_dir/"
done
cp -a -- "$repo_root/$active_version/Defs" "$artifact_dir/$active_version/"
cp -- "$built_dll" "$artifact_dir/$active_version/Assemblies/VoidShelf.dll"

python3 "$repo_root/scripts/validate-package.py" "$artifact_dir" --rimworld-dir "$rimworld_dir"
printf 'Success: packaged Void Shelf at %s\n' "$artifact_dir"
