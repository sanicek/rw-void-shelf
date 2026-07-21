#!/usr/bin/env bash
set -euo pipefail

# Installation uses a rollback-oriented sequence: validate a staged package,
# reserve the old install as a backup, place the new tree, and verify it before
# committing. State flags let the EXIT trap recover from ordinary shell exits.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
metadata="$repo_root/About/About.xml"
python3 "$repo_root/scripts/validate-source.py" "$repo_root"
package_name="$(python3 "$repo_root/scripts/project.py" "$metadata" package-name)"
mod_version="$(python3 "$repo_root/scripts/project.py" "$metadata" version)"
rimworld_input="${RIMWORLD_DIR:-${HOME:?HOME must be set}/.steam/steam/steamapps/common/RimWorld}"
artifact_dir="$repo_root/artifacts/$package_name"
release_dir="$repo_root/artifacts/releases"
install_release=false
stage_dir=""
release_extract_dir=""
backup_dir=""
old_target_moved=false
new_target_placed=false
commit_completed=false

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--release" ) ]]; then
    printf 'Usage: %s [--release]\n' "$0" >&2
    exit 2
fi
[[ $# -eq 1 ]] && install_release=true

# Resolve installation paths before mutation so rollback always addresses the
# same physical directories used by the forward path.
canonical_dir() {
    if [[ ! -d "$1" ]]; then
        printf 'Error: required directory does not exist: %s\n' "$1" >&2
        exit 1
    fi
    realpath -e -- "$1"
}

# Existing installs may predate the release metadata contract and therefore lack
# modVersion. Their stable packageId is sufficient to prove ownership before the
# first governed release replaces them.
metadata_package_id() {
    python3 -c 'import sys, xml.etree.ElementTree as ET; print(ET.parse(sys.argv[1]).getroot().findtext("packageId", "").strip())' "$1"
}

# Until commit_completed becomes true, ordinary exits and trappable signals
# remove an uncommitted stage and restore the previous target when possible.
# Cleanup errors do not mask the command status that initiated rollback.
cleanup() {
    local status=$?
    trap - EXIT
    set +e
    if [[ -n "$stage_dir" && -d "$stage_dir" ]]; then
        rm -rf -- "$stage_dir"
    fi
    if [[ -n "$release_extract_dir" && -d "$release_extract_dir" ]]; then
        rm -rf -- "$release_extract_dir"
    fi
    if [[ "$commit_completed" != true ]]; then
        if [[ "$new_target_placed" == true && ( -e "$target_dir" || -L "$target_dir" ) ]]; then
            if ! rm -rf -- "$target_dir"; then
                printf 'Error: rollback could not remove new target: %s\n' "$target_dir" >&2
            fi
        fi
        if [[ "$old_target_moved" == true && -n "$backup_dir" && ( -e "$backup_dir" || -L "$backup_dir" ) ]]; then
            if [[ ! -e "$target_dir" && ! -L "$target_dir" ]]; then
                if ! mv -T -- "$backup_dir" "$target_dir"; then
                    printf 'Error: rollback could not restore previous target from: %s\n' "$backup_dir" >&2
                fi
            else
                printf 'Error: rollback could not restore previous target because target remains: %s\n' "$target_dir" >&2
            fi
        elif [[ "$old_target_moved" != true && -n "$backup_dir" && -d "$backup_dir" ]]; then
            if ! rmdir -- "$backup_dir"; then
                printf 'Warning: retained unused backup reservation: %s\n' "$backup_dir" >&2
            fi
        fi
    fi
    exit "$status"
}

rimworld_dir="$(canonical_dir "$rimworld_input")"
mods_dir="$(canonical_dir "$rimworld_dir/Mods")"
target_dir="$mods_dir/$package_name"
exec 9<"$mods_dir"
if ! flock -n 9; then
    printf 'Error: another mod installation is in progress in %s.\n' "$mods_dir" >&2
    exit 1
fi
if [[ -L "$target_dir" ]]; then
    printf 'Error: refusing to replace symlinked install target: %s\n' "$target_dir" >&2
    exit 1
fi
if [[ -e "$target_dir" ]]; then
    existing_metadata="$target_dir/About/About.xml"
    if [[ ! -f "$existing_metadata" ]]; then
        printf 'Error: existing target is not an identifiable %s installation: %s\n' "$package_name" "$target_dir" >&2
        exit 1
    fi
    existing_package_id="$(metadata_package_id "$existing_metadata")"
    incoming_package_id="$(python3 "$repo_root/scripts/project.py" "$metadata" package-id)"
    if [[ "$existing_package_id" != "$incoming_package_id" ]]; then
        printf 'Error: install target belongs to %s, not %s.\n' "$existing_package_id" "$incoming_package_id" >&2
        exit 1
    fi
fi
trap cleanup EXIT

# A normal install builds current source. Release mode instead verifies and
# extracts the immutable candidate that will be attached to GitHub, preventing a
# successful smoke test from accidentally covering different bytes.
mkdir -p -- "$repo_root/artifacts"
exec 8<"$repo_root/artifacts"
flock 8
if [[ "$install_release" == false ]]; then
    ARTIFACT_LOCK_FD=8 "$repo_root/scripts/build.sh"
    stage_dir="$(mktemp -d -- "$mods_dir/.$package_name.stage.XXXXXX")"
    cp -a -- "$artifact_dir/." "$stage_dir/"
else
    archive="$release_dir/$package_name-v$mod_version.zip"
    checksum="$archive.sha256"
    if [[ ! -f "$archive" || ! -f "$checksum" ]]; then
        printf 'Error: --release requires %s and its .sha256 file.\n' "$archive" >&2
        exit 1
    fi
    release_extract_dir="$(mktemp -d -- "$mods_dir/.$package_name.release.XXXXXX")"
    python3 "$repo_root/scripts/extract-release.py" "$archive" "$release_extract_dir" "$package_name" --checksum "$checksum"
    stage_dir="$release_extract_dir/$package_name"
fi
python3 "$repo_root/scripts/validate-package.py" "$stage_dir" --rimworld-dir "$rimworld_dir"
staged_metadata="$stage_dir/About/About.xml"
staged_package_id="$(python3 "$repo_root/scripts/project.py" "$staged_metadata" package-id)"
staged_version="$(python3 "$repo_root/scripts/project.py" "$staged_metadata" version)"
incoming_package_id="$(python3 "$repo_root/scripts/project.py" "$metadata" package-id)"
if [[ "$staged_package_id" != "$incoming_package_id" || "$staged_version" != "$mod_version" ]]; then
    printf 'Error: staged package identity/version does not match source metadata.\n' >&2
    exit 1
fi

# Each same-filesystem rename is atomic, but the two-step replacement has a brief
# interval with no target. mktemp reserves a unique backup name; removing its
# empty directory makes that name available to mv.
if [[ -e "$target_dir" || -L "$target_dir" ]]; then
    backup_dir="$(mktemp -d -- "$mods_dir/.$package_name.backup.XXXXXX")"
    rmdir -- "$backup_dir"
    old_target_moved=true
    mv -T -- "$target_dir" "$backup_dir"
fi

new_target_placed=true
mv -T -- "$stage_dir" "$target_dir"
stage_dir=""

# Confirm source builds byte-for-byte. A release extraction is moved directly,
# so removing its now-empty parent proves no unaccounted extracted entry remains.
if [[ "$install_release" == false ]]; then
    diff -r -- "$artifact_dir" "$target_dir"
else
    rmdir -- "$release_extract_dir"
    release_extract_dir=""
fi

commit_completed=true
trap - EXIT

# Backup deletion is post-commit cleanup. Retaining it after a cleanup failure
# does not invalidate the newly verified installation.
if [[ -n "$backup_dir" ]] && ! rm -rf -- "$backup_dir"; then
    printf 'Warning: retained previous install backup at %s\n' "$backup_dir" >&2
fi
printf 'Success: installed Void Shelf at %s\n' "$target_dir"
