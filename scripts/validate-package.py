#!/usr/bin/env python3
"""Validate the structural contract of a versioned runtime-only mod package.

The package is intentionally stricter than a general RimWorld mod: it contains
only publishable metadata and version-selected runtime payloads, preserves older
recovered payloads byte-for-byte, and keeps supported-version declarations in
agreement. Validation proves package shape and integrity constraints, not the
runtime semantics of the active assembly or Defs.
"""

import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

from project import ProjectError, load_project

# These declarations define the package as an allowlist. Unexpected content is
# rejected so source, build intermediates, and stale version directories cannot
# accidentally ship.
EXPECTED_TOP_LEVEL = {"About", "LoadFolders.xml", "LICENSE", "1.5", "1.6"}
EXPECTED_VERSIONS = ("1.5", "1.6")
FORBIDDEN_NAMES = {"Source", ".git", "scripts", "bin", "obj", ".vs"}
PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROJECT_URL = "https://github.com/sanicek/rw-void-shelf"
WORKSHOP_ID = "3008773339"
FROZEN_PAYLOAD_HASHES = {
    "1.5": {
        "defs": "cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca",
        "dll": "67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20",
    },
}


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"required non-empty file is missing: {path}")


def require_directory(path: Path) -> None:
    """Require a directory whose contents cannot be redirected by a symlink."""
    if not path.is_dir() or path.is_symlink():
        fail(f"required package directory is missing or not a real directory: {path}")


def parse_xml_files(directory: Path) -> None:
    for path in sorted(directory.rglob("*.xml")):
        try:
            ET.parse(path)
        except ET.ParseError as error:
            fail(f"invalid XML in {path}: {error}")


def installed_version(rimworld_dir: Path) -> Optional[str]:
    """Read the local game version when available for advisory compatibility."""
    version_file = rimworld_dir / "Version.txt"
    if not version_file.is_file():
        print(f"Warning: RimWorld Version.txt not found: {version_file}", file=sys.stderr)
        return None
    match = re.search(r"\d+\.\d+(?:\.\d+)?", version_file.read_text(encoding="utf-8"))
    if not match:
        print(f"Warning: could not determine RimWorld version from {version_file}", file=sys.stderr)
        return None
    return match.group(0)


def load_folder_mapping(path: Path) -> Dict[str, str]:
    """Read the exact game-series-to-runtime-directory mapping."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        fail(f"invalid XML in {path}: {error}")
    if root.tag != "loadFolders" or root.attrib or (root.text and root.text.strip()):
        fail("LoadFolders.xml root must be loadFolders")
    entries = list(root)

    # Exact entries prevent metadata from advertising one set of versions while
    # RimWorld silently selects another set of payloads.
    if {entry.tag for entry in entries} != {"v1.5", "v1.6"} or len(entries) != 2:
        fail("LoadFolders.xml must contain exactly v1.5 and v1.6 mappings")
    mapping = {}
    for entry in entries:
        if entry.attrib or (entry.text and entry.text.strip()) or (entry.tail and entry.tail.strip()) or len(entry) != 1:
            fail(f"invalid LoadFolders.xml mapping for {entry.tag}")
        item = entry[0]
        if item.tag != "li" or item.attrib or len(item) != 0 or item.text is None or (item.tail and item.tail.strip()):
            fail(f"invalid LoadFolders.xml mapping for {entry.tag}")
        mapping[entry.tag] = item.text.strip()
    if mapping != {"v1.5": "1.5", "v1.6": "1.6"}:
        fail("LoadFolders.xml mappings must select matching 1.5 and 1.6 folders")
    return mapping


def validate_version(package: Path, version: str) -> None:
    """Validate one version directory as Defs plus one runtime assembly."""
    version_dir = package / version
    require_directory(version_dir)
    if {path.name for path in version_dir.iterdir()} != {"Defs", "Assemblies"}:
        fail(f"unexpected runtime content in {version_dir}")
    defs = version_dir / "Defs"
    assemblies = version_dir / "Assemblies"
    require_directory(defs)
    require_directory(assemblies)
    if {path.name for path in assemblies.iterdir()} != {"VoidShelf.dll"}:
        fail(f"unexpected runtime content in {assemblies}")
    require_file(assemblies / "VoidShelf.dll")
    def_files = sorted(defs.rglob("*.xml"))
    if not def_files:
        fail(f"no Defs XML files found under {defs}")
    if any(path.stat().st_size == 0 for path in def_files):
        fail(f"empty Defs XML file found under {defs}")
    parse_xml_files(defs)
    if version == "1.5":
        entries = {path.relative_to(version_dir).as_posix() for path in version_dir.rglob("*")}
        if entries != {"Defs", "Defs/Buildings.xml", "Assemblies", "Assemblies/VoidShelf.dll"}:
            fail("frozen 1.5 runtime must contain exactly Buildings.xml and VoidShelf.dll")


def main() -> None:
    """Validate package shape, payload integrity, and synchronized metadata."""
    # Keep the concise CLI description stable while the module narrative records
    # the validator's more detailed boundaries for maintainers.
    parser = argparse.ArgumentParser(description="Validate a versioned runtime-only RimWorld mod package.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--rimworld-dir", type=Path)
    args = parser.parse_args()

    # First establish a closed, symlink-free package boundary. Later checks can
    # then read files without following content outside the package root.
    if args.package.is_symlink():
        fail(f"package root must not be a symlink: {args.package}")
    package = args.package.resolve()
    if not package.is_dir():
        fail(f"package directory does not exist: {package}")
    if {path.name for path in package.iterdir()} != EXPECTED_TOP_LEVEL:
        fail("package must contain exactly About, LoadFolders.xml, LICENSE, 1.5, and 1.6")
    for path in package.rglob("*"):
        if path.is_symlink():
            fail(f"symlinks are not allowed in package: {path}")
        if not path.is_dir() and not path.is_file():
            fail(f"special filesystem entries are not allowed in package: {path}")
        if path.name in FORBIDDEN_NAMES:
            fail(f"generated or repository artifact is not allowed in package: {path}")

    # Validate each structural layer from shared metadata down to per-version
    # payloads. The mapping is retained for the metadata consistency check.
    about = package / "About"
    require_directory(about)
    if {path.name for path in about.iterdir()} != {"About.xml", "Preview.png", "PublishedFileId.txt"}:
        fail("About must contain exactly About.xml, Preview.png, and PublishedFileId.txt")
    require_file(about / "About.xml")
    require_file(about / "Preview.png")
    published_file_id = about / "PublishedFileId.txt"
    require_file(published_file_id)
    if published_file_id.read_text(encoding="ascii").splitlines() != [WORKSHOP_ID]:
        fail(f"About/PublishedFileId.txt must contain exactly the Workshop ID {WORKSHOP_ID}")
    load_folders = package / "LoadFolders.xml"
    require_file(load_folders)
    require_file(package / "LICENSE")
    mapping = load_folder_mapping(load_folders)
    parse_xml_files(about)
    for version in EXPECTED_VERSIONS:
        validate_version(package, version)

    # Older recovered payloads are historical artifacts, not rebuild products.
    # Hashing both Defs and DLLs makes accidental edits fail packaging.
    for version, hashes in FROZEN_PAYLOAD_HASHES.items():
        frozen_defs = package / version / "Defs" / "Buildings.xml"
        frozen_dll = package / version / "Assemblies" / "VoidShelf.dll"
        require_file(frozen_defs)
        if hashlib.sha256(frozen_defs.read_bytes()).hexdigest() != hashes["defs"]:
            fail(f"frozen {version} Buildings.xml hash mismatch")
        if hashlib.sha256(frozen_dll.read_bytes()).hexdigest() != hashes["dll"]:
            fail(f"frozen {version} VoidShelf.dll hash mismatch")

    # Player-facing metadata and runtime selection must describe the same ordered
    # versions; ordering also keeps the published metadata deterministic.
    metadata_path = about / "About.xml"
    metadata = ET.parse(metadata_path).getroot()
    try:
        project = load_project(metadata_path)
    except ProjectError as error:
        fail(str(error))
    name = metadata.findtext("name", default="").strip()
    package_id = metadata.findtext("packageId", default="").strip()
    project_url = metadata.findtext("url", default="").strip()
    versions = [element.text.strip() for element in metadata.findall("./supportedVersions/li") if element.text and element.text.strip()]
    if name != "Void Shelf":
        fail(f"About/About.xml has an unexpected name: {name!r}")
    if package_id != "Sanicek.VoidShelf" or not PACKAGE_ID.fullmatch(package_id):
        fail(f"About/About.xml has an invalid packageId: {package_id!r}")
    if project.package_name != "VoidShelf" or project_url != PROJECT_URL:
        fail(f"About/About.xml must identify VoidShelf and link to {PROJECT_URL}")
    if versions != [mapping["v1.5"], mapping["v1.6"]]:
        fail("About supportedVersions must exactly match LoadFolders.xml versions")

    # A package may validly support versions other than the local installation,
    # so this environmental mismatch is advisory rather than a package failure.
    if args.rimworld_dir:
        version = installed_version(args.rimworld_dir)
        if version:
            series = ".".join(version.split(".")[:2])
            if version not in versions and series not in versions:
                print(f"Warning: installed RimWorld {version} is not listed in supportedVersions ({', '.join(versions)}).", file=sys.stderr)

    print(f"Package validation succeeded: {package}")


if __name__ == "__main__":
    main()
