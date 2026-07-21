#!/usr/bin/env python3
"""Build one deterministic, validator-approved GitHub release archive."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from project import Project, ProjectError, load_project
from release_archive import ArchiveError, preflight_release


ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
COPY_CHUNK_SIZE = 1024 * 1024
RECORDED_CHECKSUM = re.compile(r"^\| Candidate SHA-256 \| `([0-9a-f]{64})` \|$", re.MULTILINE)


class ReleaseError(ValueError):
    """Describe state that prevents publishing an immutable release candidate."""


def archive_entry(name: str, mode: int, directory: bool = False) -> zipfile.ZipInfo:
    """Create one canonical ZIP entry independent of host timestamps and umask."""

    entry = zipfile.ZipInfo(name + ("/" if directory else ""), ARCHIVE_TIMESTAMP)
    entry.create_system = 3
    file_type = stat.S_IFDIR if directory else stat.S_IFREG
    entry.external_attr = ((file_type | mode) << 16) | (0x10 if directory else 0)
    entry.compress_type = zipfile.ZIP_DEFLATED
    return entry


def write_archive(package: Path, destination: Path) -> None:
    """Write stable names, ordering, timestamps, modes, and compressed bytes."""

    if package.is_symlink() or not package.is_dir():
        raise ReleaseError(f"release package must be a real directory: {package}")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(archive_entry(package.name, 0o755, directory=True), b"")
        for path in sorted(package.rglob("*"), key=lambda item: item.relative_to(package).as_posix()):
            relative = path.relative_to(package).as_posix()
            archive_name = f"{package.name}/{relative}"
            if path.is_symlink():
                raise ReleaseError(f"release package may not contain symlinks: {path}")
            if path.is_dir():
                archive.writestr(archive_entry(archive_name, 0o755, directory=True), b"")
            elif path.is_file():
                with path.open("rb") as source, archive.open(archive_entry(archive_name, 0o644), "w") as target:
                    shutil.copyfileobj(source, target, length=COPY_CHUNK_SIZE)
            else:
                raise ReleaseError(f"release package contains an unsupported entry: {path}")


def files_equal(first: Path, second: Path) -> bool:
    """Compare candidates without loading potentially large archives in memory."""

    if first.stat().st_size != second.stat().st_size:
        return False
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            left_chunk = left.read(COPY_CHUNK_SIZE)
            right_chunk = right.read(COPY_CHUNK_SIZE)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one archive."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_clean_worktree(repo_root: Path) -> None:
    """Reject tracked or untracked changes before release validation/building."""

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseError(f"cannot inspect release worktree: {error}") from error
    if result.stdout:
        raise ReleaseError("release packaging requires a clean worktree")


def publish_archive(
    package: Path,
    release_dir: Path,
    project: Project,
    expected_digest: str | None = None,
) -> tuple[Path, str]:
    """Publish a deterministic candidate without mutating differing same-version output."""

    if release_dir.is_symlink() or (release_dir.exists() and not release_dir.is_dir()):
        raise ReleaseError(f"release output must be a real directory: {release_dir}")
    release_dir.mkdir(parents=True, exist_ok=True)
    archive = release_dir / f"{project.package_name}-v{project.version}.zip"
    checksum = archive.with_suffix(".zip.sha256")
    if archive.is_symlink() or checksum.is_symlink():
        raise ReleaseError("release output paths may not be symlinks")
    if checksum.exists() and not checksum.is_file():
        raise ReleaseError(f"release checksum must be a regular file: {checksum}")
    if checksum.exists() and not archive.exists():
        raise ReleaseError(f"release checksum exists without its archive: {checksum}")

    temporary_fd, temporary_name = tempfile.mkstemp(prefix=f".{archive.name}.", suffix=".tmp", dir=release_dir)
    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        write_archive(package, temporary)
        preflight_release(temporary, project.package_name)
        digest = sha256_file(temporary)
        if expected_digest is not None and digest != expected_digest:
            raise ReleaseError(f"rebuilt archive does not match the accepted checksum for {project.version}")
        checksum_text = f"{digest}  {archive.name}\n"
        archive_created = False
        if archive.exists():
            if not archive.is_file() or not files_equal(archive, temporary):
                raise ReleaseError(
                    f"existing same-version candidate differs; bump modVersion or remove it after explicit review: {archive}"
                )
            if checksum.exists() and (not checksum.is_file() or checksum.read_text(encoding="ascii") != checksum_text):
                raise ReleaseError(f"existing same-version checksum differs: {checksum}")
        else:
            os.replace(temporary, archive)
            archive_created = True
        if not checksum.exists():
            checksum_fd, checksum_name = tempfile.mkstemp(prefix=f".{checksum.name}.", suffix=".tmp", dir=release_dir)
            try:
                with os.fdopen(checksum_fd, "w", encoding="ascii", newline="") as stream:
                    stream.write(checksum_text)
                os.replace(checksum_name, checksum)
            except BaseException:
                Path(checksum_name).unlink(missing_ok=True)
                if archive_created:
                    archive.unlink(missing_ok=True)
                raise
        return archive, digest
    except (ArchiveError, OSError, UnicodeError) as error:
        if isinstance(error, ReleaseError):
            raise
        raise ReleaseError(str(error)) from error
    finally:
        temporary.unlink(missing_ok=True)


def accepted_checksum(repo_root: Path, project: Project) -> str | None:
    """Read an accepted digest and prevent published versions from becoming mutable."""

    record = repo_root / "docs" / "releases" / f"{project.version}.md"
    text = record.read_text(encoding="utf-8")
    match = RECORDED_CHECKSUM.search(text)
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{project.version}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise ReleaseError("cannot inspect existing release tag")
    if result.returncode == 0:
        tagged_record = subprocess.run(
            ["git", "show", f"v{project.version}:docs/releases/{project.version}.md"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if tagged_record.returncode != 0:
            raise ReleaseError(f"published v{project.version} is missing its tagged release record")
        tagged_match = RECORDED_CHECKSUM.search(tagged_record.stdout)
        if tagged_match is None:
            raise ReleaseError(f"published v{project.version} requires a tagged candidate checksum")
        if match is None or match.group(1) != tagged_match.group(1):
            raise ReleaseError(f"current release record does not match the checksum published by v{project.version}")
        return tagged_match.group(1)
    return match.group(1) if match else None


def main() -> None:
    """Gate, validate, build, and publish while serializing artifact mutation."""

    repo_root = Path(__file__).resolve().parent.parent
    try:
        require_clean_worktree(repo_root)
        project = load_project(repo_root / "About" / "About.xml")
        expected_digest = accepted_checksum(repo_root, project)
        subprocess.run(
            [sys.executable, repo_root / "scripts" / "validate-source.py", repo_root, "--release"],
            check=True,
        )
        artifacts = repo_root / "artifacts"
        artifacts.mkdir(exist_ok=True)
        lock_fd = os.open(artifacts, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            os.set_inheritable(lock_fd, True)
            environment = {**os.environ, "ARTIFACT_LOCK_FD": str(lock_fd)}
            subprocess.run(
                [repo_root / "scripts" / "build.sh"],
                check=True,
                env=environment,
                pass_fds=(lock_fd,),
            )
            require_clean_worktree(repo_root)
            archive, digest = publish_archive(
                artifacts / project.package_name,
                artifacts / "releases",
                project,
                expected_digest,
            )
        finally:
            os.close(lock_fd)
    except (ProjectError, ReleaseError, OSError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Release archive: {archive}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
