#!/usr/bin/env python3
"""Validate a runtime-only RimWorld mod package."""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

EXPECTED_TOP_LEVEL = {"About", "Defs", "Assemblies"}
FORBIDDEN_NAMES = {"Source", ".git", "scripts", "bin", "obj", ".vs"}
PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*$")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"required non-empty file is missing: {path}")


def parse_xml_files(directory: Path) -> None:
    for path in sorted(directory.rglob("*.xml")):
        try:
            ET.parse(path)
        except ET.ParseError as error:
            fail(f"invalid XML in {path}: {error}")


def installed_version(rimworld_dir: Path) -> Optional[str]:
    version_file = rimworld_dir / "Version.txt"
    if not version_file.is_file():
        print(f"Warning: RimWorld Version.txt not found: {version_file}", file=sys.stderr)
        return None
    match = re.search(r"\d+\.\d+(?:\.\d+)?", version_file.read_text(encoding="utf-8"))
    if not match:
        print(f"Warning: could not determine RimWorld version from {version_file}", file=sys.stderr)
        return None
    return match.group(0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--rimworld-dir", type=Path)
    args = parser.parse_args()

    if args.package.is_symlink():
        fail(f"package root must not be a symlink: {args.package}")
    package = args.package.resolve()
    if not package.is_dir():
        fail(f"package directory does not exist: {package}")

    unexpected = [path.name for path in package.iterdir() if path.name not in EXPECTED_TOP_LEVEL]
    if unexpected:
        fail(f"unexpected top-level package entries: {', '.join(sorted(unexpected))}")
    for path in package.rglob("*"):
        if path.is_symlink():
            fail(f"symlinks are not allowed in package: {path}")
        if path.name in FORBIDDEN_NAMES:
            fail(f"generated or repository artifact is not allowed in package: {path}")

    about = package / "About"
    defs = package / "Defs"
    assemblies = package / "Assemblies"
    for directory in (about, defs, assemblies):
        if not directory.is_dir() or directory.is_symlink():
            fail(f"required package directory is missing or not a real directory: {directory}")
    require_file(about / "About.xml")
    require_file(assemblies / "VoidShelf.dll")
    def_files = sorted(defs.rglob("*.xml"))
    if not def_files:
        fail(f"no Defs XML files found under {defs}")
    if any(path.stat().st_size == 0 for path in def_files):
        fail("empty Defs XML file found")
    parse_xml_files(about)
    parse_xml_files(defs)

    metadata = ET.parse(about / "About.xml").getroot()
    name = metadata.findtext("name", default="").strip()
    package_id = metadata.findtext("packageId", default="").strip()
    versions = [element.text.strip() for element in metadata.findall("./supportedVersions/li") if element.text and element.text.strip()]
    if not name:
        fail("About/About.xml has an empty name")
    if not PACKAGE_ID.fullmatch(package_id):
        fail(f"About/About.xml has an invalid packageId: {package_id!r}")
    if not versions:
        fail("About/About.xml must list at least one supportedVersion")

    if args.rimworld_dir:
        version = installed_version(args.rimworld_dir)
        if version:
            series = ".".join(version.split(".")[:2])
            if version not in versions and series not in versions:
                print(f"Warning: installed RimWorld {version} is not listed in supportedVersions ({', '.join(versions)}).", file=sys.stderr)

    print(f"Package validation succeeded: {package}")


if __name__ == "__main__":
    main()
