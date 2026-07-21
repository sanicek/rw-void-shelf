"""Validate and safely extract bounded, single-root release archives."""

from __future__ import annotations

import os
import hashlib
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


MAX_ENTRIES = 10_000
MAX_MEMBER_SIZE = 256 * 1024 * 1024
MAX_TOTAL_SIZE = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
COPY_CHUNK_SIZE = 1024 * 1024
PACKAGE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z][A-Za-z0-9_]*-v\d+\.\d+\.\d+\.zip)\n$")


class ArchiveError(ValueError):
    """Describe an archive that is unsafe or outside the package contract."""


def validate_open_archive(archive: zipfile.ZipFile, package_name: str) -> None:
    """Preflight names, Unix types, and expansion bounds without writing data."""

    if not PACKAGE_NAME.fullmatch(package_name):
        raise ArchiveError(f"invalid release package name: {package_name!r}")
    entries = archive.infolist()
    if not entries or len(entries) > MAX_ENTRIES:
        raise ArchiveError("release archive has an invalid entry count")
    names = [entry.filename for entry in entries]
    if len(names) != len(set(names)):
        raise ArchiveError("release archive contains duplicate names")

    total = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != package_name:
            raise ArchiveError(f"unsafe or unexpected release entry: {entry.filename}")
        if "\\" in entry.filename:
            raise ArchiveError(f"release entry must use forward slashes: {entry.filename}")
        canonical = path.as_posix() + ("/" if entry.is_dir() else "")
        if canonical != entry.filename:
            raise ArchiveError(f"release entry is not canonically named: {entry.filename}")
        if entry.flag_bits & 0x1:
            raise ArchiveError(f"release archive may not contain encrypted entries: {entry.filename}")
        if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ArchiveError(f"unsupported compression method for: {entry.filename}")

        mode = entry.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        expected_type = stat.S_IFDIR if entry.is_dir() else stat.S_IFREG
        if file_type not in (0, expected_type):
            raise ArchiveError(f"release archive contains a link or special file: {entry.filename}")
        if entry.file_size > MAX_MEMBER_SIZE:
            raise ArchiveError(f"release member is too large: {entry.filename}")
        total += entry.file_size
        if total > MAX_TOTAL_SIZE:
            raise ArchiveError("release archive expands beyond the total size limit")
        if entry.file_size and entry.compress_size == 0:
            raise ArchiveError(f"release member has an invalid compressed size: {entry.filename}")
        if entry.compress_size and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
            raise ArchiveError(f"release member compression ratio is too high: {entry.filename}")
    if f"{package_name}/" not in names:
        raise ArchiveError(f"release archive is missing its {package_name}/ root")


def preflight_release(archive_path: Path, package_name: str) -> None:
    """Validate an archive without extracting it."""

    try:
        with zipfile.ZipFile(archive_path) as archive:
            validate_open_archive(archive, package_name)
            corrupt = archive.testzip()
            if corrupt:
                raise ArchiveError(f"release archive failed its CRC check at {corrupt}")
    except zipfile.BadZipFile as error:
        raise ArchiveError(f"invalid release ZIP: {error}") from error


def copy_verified_archive(archive_path: Path, checksum_path: Path, destination: Path) -> Path:
    """Bind one canonical sidecar to a private copy used for extraction."""

    if destination.is_symlink() or not destination.is_dir():
        raise ArchiveError(f"verification destination must be a real directory: {destination}")
    if archive_path.is_symlink() or checksum_path.is_symlink():
        raise ArchiveError("release archive and checksum must not be symlinks")
    try:
        checksum_text = checksum_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise ArchiveError(f"cannot read release checksum: {error}") from error
    match = CHECKSUM_LINE.fullmatch(checksum_text)
    if match is None or match.group(2) != archive_path.name:
        raise ArchiveError("release checksum must contain exactly the expected archive basename")
    expected = match.group(1)
    verified = destination / f".{archive_path.name}.verified"
    if verified.exists() or verified.is_symlink():
        raise ArchiveError(f"verified archive staging path already exists: {verified}")
    digest = hashlib.sha256()
    try:
        with archive_path.open("rb") as source, verified.open("xb") as target:
            while chunk := source.read(COPY_CHUNK_SIZE):
                digest.update(chunk)
                target.write(chunk)
        if digest.hexdigest() != expected:
            raise ArchiveError(f"release checksum mismatch for {archive_path.name}")
        return verified
    except (OSError, ArchiveError):
        verified.unlink(missing_ok=True)
        raise


def extract_release(archive_path: Path, destination: Path, package_name: str) -> Path:
    """Extract through a private stage, then atomically place the package root.

    The destination must be a real directory and may not already contain the
    archive root. This keeps extraction from traversing attacker-controlled
    links and gives callers an all-or-nothing package placement contract.
    """

    if not PACKAGE_NAME.fullmatch(package_name):
        raise ArchiveError(f"invalid release package name: {package_name!r}")
    if destination.is_symlink() or not destination.is_dir():
        raise ArchiveError(f"extraction destination must be a real directory: {destination}")
    target = destination / package_name
    if target.exists() or target.is_symlink():
        raise ArchiveError(f"extraction target already exists: {target}")

    stage = Path(tempfile.mkdtemp(prefix=f".{package_name}.extract.", dir=destination))
    try:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                validate_open_archive(archive, package_name)
                for entry in archive.infolist():
                    output = stage.joinpath(*PurePosixPath(entry.filename).parts)
                    if entry.is_dir():
                        output.mkdir(parents=True, exist_ok=False)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    written = 0
                    with archive.open(entry) as source, output.open("xb") as sink:
                        while chunk := source.read(COPY_CHUNK_SIZE):
                            written += len(chunk)
                            if written > entry.file_size or written > MAX_MEMBER_SIZE:
                                raise ArchiveError(f"release member exceeded its declared size: {entry.filename}")
                            sink.write(chunk)
                    if written != entry.file_size:
                        raise ArchiveError(f"release member size mismatch: {entry.filename}")
        except zipfile.BadZipFile as error:
            raise ArchiveError(f"invalid release ZIP: {error}") from error
        os.replace(stage / package_name, target)
        return target
    finally:
        shutil.rmtree(stage, ignore_errors=True)
