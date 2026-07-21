# Design

## Purpose

Void Shelf provides an intentional item sink using RimWorld's familiar shelf
storage interface. Players choose accepted items with the normal storage filter;
the shelf permanently destroys every held item on its rare-tick schedule. The
default empty filter and Low priority reduce, but cannot eliminate, the risk of
accidental loss.

This document preserves runtime and compatibility decisions that must survive
implementation changes. Release-specific risks and acceptance evidence belong
in [the release records](RELEASES.md).

## Versioned Runtime Model

`LoadFolders.xml` loads shared root content followed by exactly one runtime tree.
Root content currently supplies translations. RimWorld 1.5 loads recovered Defs
and a recovered assembly; those files are immutable and protected by SHA-256
checks in both the build and package validator. RimWorld 1.6 loads maintained
Defs and an assembly compiled from `Source/VoidShelf`.

The 1.6 `VoidShelf` ThingDef inherits `StorageShelfBase`, retaining normal game
storage, filters, priorities, and hauling. `CompProperties_DestroyerShelf`
attaches `CompDestroyerShelf`; each rare tick, the component snapshots the slot
group and destroys all held things except its parent. A missing slot group is a
valid no-op. Combat Extended motivated the item-sink use case but is not a
dependency.

## Localization Model

The maintained 1.6 ThingDef is the English source for `VoidShelf.label` and
`VoidShelf.description`. Simplified Chinese, French, German, Russian, and Spanish
override those fields through root-level `DefInjected/ThingDef/Buildings.xml`
catalogs. Root routing makes the same catalogs apply to both game versions while
leaving the checksum-frozen 1.5 Def unchanged.

The validator derives required keys from the active Def, requires the exact
supported language tree, and rejects missing, duplicate, empty, or unchanged
English values. There is no keyed catalog because the current C# strings are
diagnostic logs rather than player-facing UI.

## Durable Contracts

- Package ID `Sanicek.VoidShelf` identifies the mod in active saves and mod
  lists.
- Workshop item ID `3008773339` identifies the recovered publication and must not
  be replaced during GitHub release work.
- DefName `VoidShelf` and runtime types `VoidShelf.CompProperties_DestroyerShelf`
  and `VoidShelf.CompDestroyerShelf` are save- and XML-sensitive identities.
- RimWorld 1.5 and 1.6 remain supported until an intentional major-version
  decision changes the support contract.
- English and the five translated languages remain synchronized for every
  player-facing Def field included in the localization contract.
- The 1.5 Def and DLL remain byte-for-byte frozen at their documented hashes.
- The shelf remains an irreversible item sink driven by rare ticks, not a hidden
  inventory, conversion recipe, or recoverable deletion queue.
- Normal shelf storage settings remain player-controlled; the default filter is
  empty and the default priority is Low.

Rename or reinterpretation of these identities and behaviors requires an
explicit migration decision, release-record warning, and appropriate Semantic
Version increment.

## Failure Behavior

If the component has no slot group, it performs no destruction. Destruction
iterates a snapshot because removing an item mutates the held-things collection,
and the parent shelf is explicitly excluded. Each destruction is logged for
diagnosis, but there is no undo path after `Thing.Destroy()` succeeds.

Build and package failures are fail-closed. A mismatched game series, missing
managed assembly, changed frozen hash, invalid XML, inconsistent version routing,
symlink, or unexpected package content prevents packaging. These checks prove
shape and historical integrity; only an in-game smoke test proves runtime
behavior.

## Version Rollover

When a new RimWorld series becomes active, first validate the outgoing active
series and freeze its final Def and DLL with documented checksums. Then add the
new Def tree, move compilation to the new series, and update `About/About.xml`,
`LoadFolders.xml`, the build allowlist, package validator, README, and this design
record together. Never regenerate the recovered 1.5 payload from current source.
