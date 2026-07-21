# Release Policy

## Scope

Void Shelf releases are local and operator-driven. Hosted CI/CD is intentionally
absent. This policy governs GitHub packages without replacing the recovered Steam
Workshop identity `3008773339`; Workshop updates remain separate, explicit
publication actions.

## Versioning

Void Shelf uses Semantic Versioning. `About/About.xml` is the single source for
the current version through `modVersion`. Installable archives use
`VoidShelf-vMAJOR.MINOR.PATCH.zip`, and published tags use the matching
`vMAJOR.MINOR.PATCH` form.

- PATCH contains compatible fixes or packaging corrections.
- MINOR adds backward-compatible gameplay or user-facing functionality.
- MAJOR intentionally changes a save, Def identity, package identity, or another
  compatibility contract, or drops an already supported RimWorld series.

Any change to generated package bytes or runtime behavior is release-bearing.
Repository-only documentation, process, tests, and tooling changes do not need a
version bump when package output is unchanged. Tooling that changes package
output is release-bearing.

## Historical Payload Boundary

The RimWorld 1.5 Def and DLL were recovered from the published Workshop item and
are immutable release inputs. Every build checks their SHA-256 hashes. Active
source and Def maintenance targets RimWorld 1.6; a future rollover must freeze
the outgoing active payload and update all version-routing contracts together.

## Release Records

Copy [`releases/EXAMPLE.md`](releases/EXAMPLE.md) to
`docs/releases/MAJOR.MINOR.PATCH.md`. Each record also serves as GitHub release
notes and records changes, update risks, exact build inputs, source revision,
archive checksum, and representative smoke-test acceptance.

- [1.1.0](releases/1.1.0.md) - shared translations for five additional languages
- [1.0.0](releases/1.0.0.md) - first governed stable release

`PENDING` is a publication blocker, not an acceptable value in a published
record. Historical facts that cannot be reconstructed must instead be described
honestly as unavailable and scoped to the relevant recovered payload.

## Candidate Acceptance

1. On a feature branch, select the next version, update `modVersion`, and add its
   release record.
2. Run `scripts/test.sh` and the affected build validation, then commit the
   candidate so its source revision is fixed and the worktree is clean.
3. Run `python3 scripts/package-release.py`. It validates release source, builds
   the package, and writes `artifacts/releases/VoidShelf-vMAJOR.MINOR.PATCH.zip`
   plus its `.zip.sha256` sidecar. Canonical entry ordering, timestamps, modes,
   compression, and paths make repeated builds deterministic. Different
   same-version bytes are rejected rather than overwritten.
4. Run `scripts/install-local.sh --release`. It verifies the sidecar, safely
   extracts the bounded single-root archive, validates the extracted package,
   and transactionally installs those exact bytes without rebuilding.
5. Complete one representative RimWorld smoke test and record the result,
   checksum, source revision, exact game build, and tool versions.
6. Commit the acceptance record, push it to the same branch, update the draft PR,
   and only then make the PR ready for merge. The ordinary
   `scripts/install-local.sh` source-build path is development validation, not
   exact-candidate evidence.

## Publication

1. Merge the accepted release-bearing PR through protected `main`.
2. Synchronize a clean local `main` and run
   `python3 scripts/package-release.py` with the recorded inputs. When the tested
   candidate remains under `artifacts/releases/`, the packager compares the
   rebuilt bytes instead of replacing it; otherwise compare the reproduced
   checksum with the candidate record.
3. Require the final SHA-256 to match the accepted candidate. If it differs,
   install and smoke-test the final archive and update the record before
   publication.
4. Create and push an annotated `vMAJOR.MINOR.PATCH` tag at the release commit.
5. Create the GitHub release with `gh release create`, attaching the installable
   ZIP and checksum sidecar and using the matching release record as notes.

Merge approval for an accepted release-bearing PR also authorizes these
post-merge GitHub publication steps unless checksum verification fails. GitHub's
automatically generated source archives are snapshots and must never be
presented as installable RimWorld packages.
