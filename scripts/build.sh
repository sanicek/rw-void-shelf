#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rimworld_input="${RIMWORLD_DIR:-${HOME:?HOME must be set}/.steam/steam/steamapps/common/RimWorld}"
project="$repo_root/Source/VoidShelf/VoidShelf.csproj"
artifact_dir="$repo_root/artifacts/VoidShelf"
built_dll="$repo_root/Source/VoidShelf/bin/Release/net472/VoidShelf.dll"

canonical_dir() {
    if [[ ! -d "$1" ]]; then
        printf 'Error: required directory does not exist: %s\n' "$1" >&2
        exit 1
    fi
    realpath -e -- "$1"
}

rimworld_dir="$(canonical_dir "$rimworld_input")"
managed_input="${RIMWORLD_MANAGED_DIR:-$rimworld_dir/RimWorldLinux_Data/Managed}"
managed_dir="$(canonical_dir "$managed_input")"

if [[ ! -f "$project" || ! -f "$managed_dir/Assembly-CSharp.dll" ]]; then
    printf 'Error: project or Assembly-CSharp.dll is missing.\n' >&2
    exit 1
fi

printf 'Repository: %s\nRimWorld: %s\nManaged DLLs: %s\n' "$repo_root" "$rimworld_dir" "$managed_dir"
dotnet restore "$project" --locked-mode
dotnet build "$project" --configuration Release --no-restore -p:RimWorldManagedDir="$managed_dir"

if [[ ! -f "$built_dll" ]]; then
    printf 'Error: build output is missing: %s\n' "$built_dll" >&2
    exit 1
fi
rm -rf -- "$artifact_dir"
mkdir -p -- "$artifact_dir/Assemblies"
cp -a -- "$repo_root/About" "$artifact_dir/"
cp -a -- "$repo_root/Defs" "$artifact_dir/"
cp -- "$built_dll" "$artifact_dir/Assemblies/VoidShelf.dll"

python3 "$repo_root/scripts/validate-package.py" "$artifact_dir" --rimworld-dir "$rimworld_dir"
printf 'Success: packaged Void Shelf at %s\n' "$artifact_dir"
