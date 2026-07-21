# Void Shelf

Void Shelf is a RimWorld storage building that permanently destroys items placed
on it. Use its storage settings carefully: anything stored on the shelf is lost.

## Installation

The recovered Steam Workshop publication is
[item 3008773339](https://steamcommunity.com/sharedfiles/filedetails/?id=3008773339).
When a governed GitHub release is published, its attached
`VoidShelf-vMAJOR.MINOR.PATCH.zip` will be the supported manual download. Extract
the archive's `VoidShelf` directory into RimWorld's `Mods` directory and enable
it in the mod manager. GitHub-generated source archives are repository snapshots,
not installable mods.

The current governed candidate is documented in
[`docs/releases/1.0.0.md`](docs/releases/1.0.0.md); use only a published archive
whose candidate record contains its checksum and acceptance evidence.

## Recovery Status

This repository contains source and shipped artifacts recovered from Workshop
item [3008773339](https://steamcommunity.com/sharedfiles/filedetails/?id=3008773339).
The recovered publication ID is preserved in `About/PublishedFileId.txt`. The mod
supports RimWorld 1.5 and 1.6 through versioned runtime folders.

## Build And Local Install

Prerequisites: Linux, .NET SDK 10 (or a compatible SDK with .NET Framework 4.7.2
targeting-pack support), Python 3, and a RimWorld installation. The default
RimWorld location is `$HOME/.steam/steam/steamapps/common/RimWorld`.

Install the locally built mod with one command:

```bash
./scripts/install-local.sh
```

To use a different game installation, set `RIMWORLD_DIR`:

```bash
RIMWORLD_DIR=/path/to/RimWorld ./scripts/install-local.sh
```

Build without installing with:

```bash
./scripts/build.sh
```

The resulting runtime-only package is written to `artifacts/VoidShelf/`:

```text
About/
LoadFolders.xml
1.5/
  Defs/
  Assemblies/VoidShelf.dll
1.6/
  Defs/
  Assemblies/VoidShelf.dll
LICENSE
```

`LoadFolders.xml` selects the matching `1.5/` or `1.6/` folder at runtime. The
1.5 Def and DLL are immutable recovered shipped artifacts, checksum-protected as
`cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca` and
`67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20`.
Current source builds the active 1.6 DLL only; 1.5 was not newly rebuilt or
retested. The build validates package structure, XML, LoadFolders mappings, and
frozen payload hashes.

## Tests And Validation

Run host-independent tooling tests with:

```bash
./scripts/test.sh
```

These tests cover metadata and source contracts, deterministic archive bytes,
same-version candidate immutability, clean-worktree release gates, and rejection
of unsafe archive forms. They do not require RimWorld, .NET, or a network.

`./scripts/build.sh` is the integration check: it restores with the lock file,
compiles the active 1.6 assembly with warnings as errors, checks both frozen 1.5
hashes, assembles an allowlisted package, parses its XML, and validates its
version routing and package shape.

To revalidate an existing package explicitly:

```bash
python3 scripts/validate-package.py artifacts/VoidShelf \
  --rimworld-dir "${RIMWORLD_DIR:-$HOME/.steam/steam/steamapps/common/RimWorld}"
```

Automated validation does not prove gameplay behavior. After gameplay changes,
install locally and complete the manual smoke test below.

### Manual Smoke Test

1. Enable Void Shelf in RimWorld's mod list.
2. Start or load a colony and build a Void Shelf.
3. Confirm its storage filter starts empty and its priority starts Low.
4. Intentionally permit a disposable item, haul it onto the shelf, and confirm
   it is permanently destroyed on the shelf's rare tick.

### Future Version Rollover

When 1.7 is validated, copy and freeze the final 1.6 DLL into tracked
`1.6/Assemblies/`, add 1.6 to the frozen version/hash configuration, create 1.7
Defs, change the active build/package target to 1.7, and extend
`About/About.xml`, `LoadFolders.xml`, and the validator. This keeps every prior
payload packaged and checksum-protected.

## Release Candidates

A release-bearing change must update `About/About.xml` and its version record,
then produce a deterministic `VoidShelf-vMAJOR.MINOR.PATCH.zip` from a clean
candidate commit. Candidate acceptance must install and test that exact ZIP
without rebuilding it, and record its SHA-256 checksum and toolchain versions.

From the clean candidate commit, create the archive and checksum sidecar:

```bash
python3 scripts/package-release.py
```

The packager fixes ZIP timestamps, permissions, entry order, compression, and
single-root layout. It validates the source and assembled package, rejects a
dirty worktree, preflights the resulting archive, and refuses to overwrite
different same-version candidate bytes. Outputs are written to
`artifacts/releases/`.

Install the exact checksummed candidate without rebuilding:

```bash
./scripts/install-local.sh --release
```

Release mode verifies the `.zip.sha256` sidecar, rejects traversal, links,
special files, duplicate names, noncanonical paths, and unsafe expansion, then
validates and transactionally installs the extracted package. The ordinary
`./scripts/install-local.sh` remains the source-build development path and is not
candidate acceptance evidence. See [the release policy](docs/RELEASES.md).

After acceptance and merge, rebuild from clean `main`; publish only if the final
archive checksum matches the tested candidate. If it differs, install and smoke
test the final archive again before tagging or publishing.

## Troubleshooting And Issue Reports

Reports are welcome in [GitHub Issues](https://github.com/sanicek/rw-void-shelf/issues)
or on the recovered Workshop page. Include:

- RimWorld and Void Shelf versions.
- A short reproduction sequence and whether it also occurs in a new colony.
- The active mod list and load order.
- Whether the 1.5 frozen payload or active 1.6 payload was loaded.
- A link to the relevant `Player.log`, especially for startup or loading errors.

On Windows, `Player.log` is normally under
`%USERPROFILE%\AppData\LocalLow\Ludeon Studios\RimWorld by Ludeon Studios`. On
Linux it is under
`~/.config/unity3d/Ludeon Studios/RimWorld by Ludeon Studios`. Upload the log to
a paste or file-sharing service and link it instead of pasting the entire log
into a comment.

## Repository Layout

- `About/` — mod metadata, Workshop item ID, and preview image
- `1.5/` — immutable recovered 1.5 runtime Defs and DLL
- `1.6/` — active 1.6 Defs; its DLL is generated only in packages
- `Source/VoidShelf/` — Visual Studio solution, project, and C# source
- `scripts/` — build, package validation, and local-install helpers
- `docs/` — durable design decisions and release governance
- `artwork/` — provenance and approval policy for tracked images
- `WORKSHOP_DESCRIPTION.md` — paste-ready Steam Workshop description in BBCode

## Maintainer Documentation

- [Design and compatibility contracts](docs/DESIGN.md)
- [Release policy and records](docs/RELEASES.md)
- [Artwork provenance and approval](artwork/README.md)
- [Repository workflow](AGENTS.md)

## Maintenance Style

Maintained source follows the literate programming convention in `AGENTS.md`:
files and nontrivial phases introduce their purpose, invariants, and tradeoffs
before the implementation. Comments explain why a constraint exists rather than
repeat what the syntax already says, and must change with the behavior they
describe.

Apply that convention to the active C#, scripts, build configuration, mod
metadata, version routing, and 1.6 Defs. Simple declarative files need only the
context required to maintain their contracts. Do not rewrite generated output,
dependency lockfiles, solution files, binaries, artwork, publishing IDs, legal
text, or the checksum-frozen 1.5 payload to add commentary; document their
contracts in the maintained code that produces or validates them instead.
