#!/usr/bin/env python3
"""Validate repository inputs before copy or destructive artifact operations.

Void Shelf has one checksum-frozen recovered runtime for RimWorld 1.5 and one
maintained runtime for 1.6. The checks below preserve that split before a build
can recreate artifacts or a release can claim a source revision.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from project import ProjectError, load_project


EXPECTED_VERSIONS = ("1.5", "1.6")
ACTIVE_VERSION = "1.6"
FROZEN_PAYLOAD_HASHES = {
    "1.5": {
        "Defs/Buildings.xml": "cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca",
        "Assemblies/VoidShelf.dll": "67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20",
    }
}
PACKAGE_INPUTS = ("About", "LoadFolders.xml", "LICENSE", *EXPECTED_VERSIONS)


class SourceError(ValueError):
    """Describe source state that cannot produce a trustworthy package."""


def require(condition: bool, message: str) -> None:
    """Raise one domain error so API and CLI callers share diagnostics."""

    if not condition:
        raise SourceError(message)


def git_result(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run a read-only Git query and convert execution failures to source errors."""

    try:
        return subprocess.run(["git", *arguments], cwd=repo_root, check=False, capture_output=True)
    except OSError as error:
        raise SourceError(f"cannot run git {' '.join(arguments)}: {error}") from error


def ignored(repo_root: Path, path: Path) -> bool:
    """Determine whether a build input would be absent from a clean checkout."""

    result = git_result(repo_root, "check-ignore", "--quiet", "--", str(path.relative_to(repo_root)))
    require(result.returncode in (0, 1), f"git check-ignore failed for {path}")
    return result.returncode == 0


def validate_real_tree(repo_root: Path, source: Path, label: str) -> None:
    """Reject links, escapes, and ignored files throughout one maintained tree."""

    require(source.exists() or source.is_symlink(), f"required {label} is missing: {source}")
    candidates = [source, *source.rglob("*")] if source.is_dir() and not source.is_symlink() else [source]
    for path in candidates:
        require(not path.is_symlink(), f"{label} may not contain symlinks: {path}")
        require(path.resolve().is_relative_to(repo_root), f"{label} escapes repository: {path}")
        require(not ignored(repo_root, path), f"ignored file or directory would enter {label}: {path}")


def validate_source(repo_root: Path, release: bool = False) -> None:
    """Validate identity, runtime layout, frozen bytes, and optional release record."""

    repo_root = repo_root.resolve()
    try:
        project = load_project(repo_root / "About" / "About.xml")
    except ProjectError as error:
        raise SourceError(str(error)) from error
    require(project.package_id == "Sanicek.VoidShelf", "packageId must remain Sanicek.VoidShelf")
    require(project.package_name == "VoidShelf", "package output name must remain VoidShelf")
    require(project.supported_versions == EXPECTED_VERSIONS, "supportedVersions must be ordered 1.5, 1.6")

    artifacts = repo_root / "artifacts"
    require(not artifacts.is_symlink(), "artifacts must not be a symlink")
    if artifacts.exists():
        require(artifacts.is_dir(), "artifacts must be a directory")
        require(artifacts.resolve() == artifacts, "artifacts must resolve inside the repository")
    require(not (repo_root / "Assemblies").exists(), "root Assemblies is unsupported; use versioned runtimes")

    for name in PACKAGE_INPUTS:
        validate_real_tree(repo_root, repo_root / name, "package source")
    for version in EXPECTED_VERSIONS:
        runtime = repo_root / version
        expected_entries = {"Defs", "Assemblies"} if version == "1.5" else {"Defs"}
        require(
            {path.name for path in runtime.iterdir()} == expected_entries,
            f"unexpected source runtime shape for {version}",
        )
    frozen_entries = {path.relative_to(repo_root / "1.5").as_posix() for path in (repo_root / "1.5").rglob("*")}
    expected_frozen_entries = {"Defs", "Assemblies", *FROZEN_PAYLOAD_HASHES["1.5"]}
    require(frozen_entries == expected_frozen_entries, "frozen 1.5 runtime contains unexpected entries")
    for version, files in FROZEN_PAYLOAD_HASHES.items():
        for relative, expected in files.items():
            path = repo_root / version / relative
            require(path.is_file(), f"frozen {version} payload is missing: {relative}")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"frozen {version} payload hash mismatch: {relative}")

    source_root = repo_root / "Source"
    require(not source_root.is_symlink() and source_root.is_dir(), "Source must be a real directory")
    for path in [source_root, *source_root.rglob("*")]:
        require(not path.is_symlink(), f"C# source may not contain symlinks: {path}")
        require(path.resolve().is_relative_to(repo_root), f"C# source escapes repository: {path}")
        generated = any(part in {"bin", "obj"} for part in path.relative_to(source_root).parts)
        if not generated:
            require(not ignored(repo_root, path), f"ignored C# build input is not reproducible: {path}")
    project_file = source_root / project.package_name / f"{project.package_name}.csproj"
    require(project_file.is_file(), f"active {ACTIVE_VERSION} project is missing: {project_file}")

    if release:
        record = repo_root / "docs" / "releases" / f"{project.version}.md"
        require(record.is_file() and not record.is_symlink(), f"release record is required as a regular file: {record.relative_to(repo_root)}")
        require(record.resolve().is_relative_to(repo_root), "release record must remain inside the repository")
        require(not ignored(repo_root, record), "release record may not be ignored")
        tracked = git_result(repo_root, "ls-files", "--error-unmatch", "--", str(record.relative_to(repo_root)))
        require(tracked.returncode == 0, "release record must be tracked by Git")


def main() -> None:
    """Expose pre-build and stricter pre-release validation modes."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    try:
        validate_source(args.repo, args.release)
    except SourceError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Validated package source: {args.repo.resolve()}")


if __name__ == "__main__":
    main()
