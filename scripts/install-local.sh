#!/usr/bin/env bash
set -euo pipefail

# Installation uses a rollback-oriented sequence: validate a staged package,
# reserve the old install as a backup, place the new tree, and verify it before
# committing. State flags let the EXIT trap recover from ordinary shell exits.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rimworld_input="${RIMWORLD_DIR:-${HOME:?HOME must be set}/.steam/steam/steamapps/common/RimWorld}"
artifact_dir="$repo_root/artifacts/VoidShelf"
stage_dir=""
backup_dir=""
old_target_moved=false
new_target_placed=false
commit_completed=false

# Resolve installation paths before mutation so rollback always addresses the
# same physical directories used by the forward path.
canonical_dir() {
    if [[ ! -d "$1" ]]; then
        printf 'Error: required directory does not exist: %s\n' "$1" >&2
        exit 1
    fi
    realpath -e -- "$1"
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
target_dir="$mods_dir/VoidShelf"
trap cleanup EXIT

# Build first, then copy into the game filesystem and validate that exact staged
# tree. The live mod remains untouched while either operation can still fail.
"$repo_root/scripts/build.sh"

stage_dir="$(mktemp -d -- "$mods_dir/.VoidShelf.stage.XXXXXX")"
cp -a -- "$artifact_dir/." "$stage_dir/"
python3 "$repo_root/scripts/validate-package.py" "$stage_dir" --rimworld-dir "$rimworld_dir"

# Each same-filesystem rename is atomic, but the two-step replacement has a brief
# interval with no target. mktemp reserves a unique backup name; removing its
# empty directory makes that name available to mv.
if [[ -e "$target_dir" || -L "$target_dir" ]]; then
    backup_dir="$(mktemp -d -- "$mods_dir/.VoidShelf.backup.XXXXXX")"
    rmdir -- "$backup_dir"
    old_target_moved=true
    mv -T -- "$target_dir" "$backup_dir"
fi

new_target_placed=true
mv -T -- "$stage_dir" "$target_dir"
stage_dir=""

# Confirm the installed bytes match the validated artifact before discarding the
# rollback path. The trap remains armed until this comparison succeeds.
diff -r -- "$artifact_dir" "$target_dir"

commit_completed=true
trap - EXIT

# Backup deletion is post-commit cleanup. Retaining it after a cleanup failure
# does not invalidate the newly verified installation.
if [[ -n "$backup_dir" ]] && ! rm -rf -- "$backup_dir"; then
    printf 'Warning: retained previous install backup at %s\n' "$backup_dir" >&2
fi
printf 'Success: installed Void Shelf at %s\n' "$target_dir"
