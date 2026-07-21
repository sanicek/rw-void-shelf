#!/usr/bin/env bash
set -euo pipefail

# Tooling tests are host-independent and intentionally do not build assemblies.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m unittest discover -s "$repo_root/tests" -p 'test_tooling.py' -v
