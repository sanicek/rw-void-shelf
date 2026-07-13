# Void Shelf

Void Shelf is a RimWorld storage building that permanently destroys items placed
on it. Use its storage settings carefully: anything stored on the shelf is lost.

## Recovery status

This repository contains the shipped source recovered from Workshop item
[3008773339](https://steamcommunity.com/sharedfiles/filedetails/?id=3008773339).
It currently targets RimWorld 1.6.

## Build and local install

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
Defs/
Assemblies/VoidShelf.dll
```

The build validates the package structure and XML. When a RimWorld installation
is supplied, validation warns if its version is not listed in `About/About.xml`.
The current metadata targets RimWorld 1.6, matching the locally validated game
version.

### Manual smoke test

1. Enable Void Shelf in RimWorld's mod list.
2. Start or load a colony and build a Void Shelf.
3. Set its storage filter, place a permitted item on it, and confirm the item is
   removed on the shelf's rare tick.

## Repository layout

- `About/` — mod metadata, Workshop item ID, and preview image
- `Defs/` — RimWorld definitions
- `Source/VoidShelf/` — Visual Studio solution, project, and C# source
- `scripts/` — build, package validation, and local-install helpers
