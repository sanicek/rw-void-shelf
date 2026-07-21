#!/usr/bin/env python3
"""Preflight and safely extract one locally produced release archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from release_archive import ArchiveError, copy_verified_archive, extract_release


def main() -> None:
    """Provide the extraction contract to future installer integration."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("package_name")
    parser.add_argument("--checksum", type=Path)
    args = parser.parse_args()
    verified = None
    try:
        archive = args.archive
        if args.checksum is not None:
            verified = copy_verified_archive(args.archive, args.checksum, args.destination)
            archive = verified
        package = extract_release(archive, args.destination, args.package_name)
    except (ArchiveError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        if verified is not None:
            verified.unlink(missing_ok=True)
    print(f"Extracted release: {package}")


if __name__ == "__main__":
    main()
