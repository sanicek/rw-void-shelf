# Void Shelf

Void Shelf is a RimWorld storage building that permanently destroys items placed
on it. Use its storage settings carefully: anything stored on the shelf is lost.

## Recovery status

This repository contains source and shipped artifacts recovered from Workshop
item [3008773339](https://steamcommunity.com/sharedfiles/filedetails/?id=3008773339).
It supports RimWorld 1.5 and 1.6 through versioned runtime folders.

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
LoadFolders.xml
1.5/
  Defs/
  Assemblies/VoidShelf.dll
1.6/
  Defs/
  Assemblies/VoidShelf.dll
```

`LoadFolders.xml` selects the matching `1.5/` or `1.6/` folder at runtime. The
1.5 Def and DLL are immutable recovered shipped artifacts, checksum-protected as
`cbf0d16d5bc11a5f0fb2351b994d0cb7c68bfa8738aa3f85b4a2a49270c6baca` and
`67b0c3c907b46e05913be541dd04cee488fc8c7ddbb6ed5877d92c01e71b6f20`.
Current source builds the active 1.6 DLL only; 1.5 was not newly rebuilt or
retested. The build validates package structure, XML, LoadFolders mappings, and
frozen payload hashes.

### Future version rollover

When 1.7 is validated, copy and freeze the final 1.6 DLL into tracked
`1.6/Assemblies/`, add 1.6 to the frozen version/hash configuration, create 1.7
Defs, change the active build/package target to 1.7, and extend
`About/About.xml`, `LoadFolders.xml`, and the validator. This keeps every prior
payload packaged and checksum-protected.

### Manual smoke test

1. Enable Void Shelf in RimWorld's mod list.
2. Start or load a colony and build a Void Shelf.
3. Set its storage filter, place a permitted item on it, and confirm the item is
   removed on the shelf's rare tick.

## Repository layout

- `About/` — mod metadata, Workshop item ID, and preview image
- `1.5/` — immutable recovered 1.5 runtime Defs and DLL
- `1.6/` — active 1.6 Defs; its DLL is generated only in packages
- `Source/VoidShelf/` — Visual Studio solution, project, and C# source
- `scripts/` — build, package validation, and local-install helpers
- `WORKSHOP_DESCRIPTION.md` — paste-ready Steam Workshop description in BBCode
