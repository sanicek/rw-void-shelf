#!/usr/bin/env python3
"""Read the package identity shared by build, install, and release tools.

About/About.xml is the single source of truth. Derived filesystem names come
from the final package-id component so another configuration value cannot drift
away from the identity RimWorld uses.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PACKAGE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")
RIMWORLD_VERSION = re.compile(r"^\d+\.\d+$")
RESERVED_PACKAGE_NAMES = {"build", "releases"}


class ProjectError(ValueError):
    """Report invalid project metadata without exposing parser internals."""


@dataclass(frozen=True)
class Project:
    """Identity and compatibility fields needed by downstream tooling."""

    name: str
    author: str
    package_id: str
    package_name: str
    version: str
    supported_versions: tuple[str, ...]


def load_project(metadata: Path) -> Project:
    """Load the unique, non-empty metadata fields used to route output."""

    try:
        root = ET.parse(metadata).getroot()
    except (OSError, ET.ParseError) as error:
        raise ProjectError(f"cannot read metadata {metadata}: {error}") from error

    def required(tag: str) -> str:
        elements = root.findall(tag)
        if len(elements) != 1:
            raise ProjectError(f"About/About.xml requires exactly one <{tag}>")
        value = elements[0].text.strip() if elements[0].text else ""
        if not value:
            raise ProjectError(f"About/About.xml requires a non-empty <{tag}>")
        return value

    name = required("name")
    author = required("author")
    package_id = required("packageId")
    version = required("modVersion")
    if not PACKAGE_ID.fullmatch(package_id):
        raise ProjectError(f"invalid packageId: {package_id!r}")
    if not SEMVER.fullmatch(version):
        raise ProjectError(f"modVersion is not MAJOR.MINOR.PATCH SemVer: {version!r}")

    versions_element = root.find("supportedVersions")
    versions = tuple(
        item.text.strip()
        for item in (() if versions_element is None else versions_element.findall("li"))
        if item.text and item.text.strip()
    )
    if not versions or len(set(versions)) != len(versions):
        raise ProjectError("supportedVersions must contain unique versions")
    if any(not RIMWORLD_VERSION.fullmatch(item) for item in versions):
        raise ProjectError(f"invalid supported RimWorld version in {versions!r}")

    package_name = package_id.rsplit(".", 1)[1]
    if package_name.lower() in RESERVED_PACKAGE_NAMES:
        raise ProjectError(f"packageId final component is reserved by build tooling: {package_name!r}")
    return Project(name, author, package_id, package_name, version, versions)


def main() -> None:
    """Expose stable scalar fields for shell scripts during later integration."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument(
        "field",
        choices=("name", "author", "package-id", "package-name", "version", "supported-versions"),
    )
    args = parser.parse_args()
    try:
        project = load_project(args.metadata)
    except ProjectError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    values = {
        "name": project.name,
        "author": project.author,
        "package-id": project.package_id,
        "package-name": project.package_name,
        "version": project.version,
        "supported-versions": " ".join(project.supported_versions),
    }
    print(values[args.field])


if __name__ == "__main__":
    main()
