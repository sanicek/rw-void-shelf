# AGENTS.md

## Project Conventions

- Keep generated builds, release archives, and local RimWorld files out of
  version control.
- Preserve recovered Workshop identity `3008773339`; `About/PublishedFileId.txt`
  is historical publication metadata, not a replaceable bootstrap value.
- Treat the recovered RimWorld 1.5 Def and DLL as immutable, checksum-frozen
  payloads. Maintained source and Defs target RimWorld 1.6 until an intentional
  version rollover updates the build, validator, metadata, and documentation.
- Validate a built package with
  `python3 scripts/validate-package.py artifacts/VoidShelf --rimworld-dir "$RIMWORLD_DIR"`.
- Treat `About/About.xml` `modVersion` as the single release version. Tags and
  GitHub releases use the matching `vMAJOR.MINOR.PATCH` form, and the canonical
  project URL is `https://github.com/sanicek/rw-void-shelf`.
- Any change that alters the generated installable package or runtime behavior
  is release-bearing. The same pull request must select the next Semantic
  Version, update `modVersion`, add its release record, and complete candidate
  acceptance before merge.
- Repository-only documentation, process, tests, and tooling changes need no
  version bump when package output is unchanged. Tooling that changes package
  output is release-bearing.

## Engineering Guardrails

- Prefer the simplest engine-native or declarative solution. Do not introduce a
  workaround whose complexity, compatibility risk, or upkeep is disproportionate
  to the issue without explicit user approval.
- Before requesting approval for a complex workaround, explain the underlying
  issue, mechanism, implementation cost, compatibility risks, and simpler
  alternatives. A general request to fix an issue is not approval.
- Any new Harmony patch requires explicit user approval. Explain why XML,
  inheritance, composition, or a supported public API cannot solve the problem,
  and identify the target, patch type, scope, and compatibility risk.

## Artwork Workflow

- Follow `artwork/README.md`. The repository currently has no automated artwork
  pipeline, so do not claim ad hoc image processing is reproducible.
- Keep credentials, raw generations, receipts, candidates, and review sheets out
  of version control. Only explicitly approved final outputs enter `About/`.
- Do not replace the recovered Workshop preview without explicit user selection
  and approval. Record provenance, processing, and validation when replacement
  artwork is accepted.

## Localization Workflow

- English ThingDef text in the maintained 1.6 Def is the localization source.
  Do not add an English `DefInjected` copy or edit the frozen 1.5 Def.
- Root `Languages/` content supplies `VoidShelf.label` and
  `VoidShelf.description` to both supported game versions. Keep complete
  ChineseSimplified, French, German, Russian, and Spanish catalogs at the exact
  shared `DefInjected/ThingDef/Buildings.xml` path.
- Preserve key coverage, non-empty translated values, and natural
  game-appropriate terminology. A translation change alters package output and
  is release-bearing.
- If future C# code adds player-facing text, introduce a stable `VoidShelf_`
  keyed English source catalog and matching catalogs for every supported
  language. Diagnostic log messages do not require translation.

## Literate Programming

- Write all maintained code in a literate programming style: present each file and nontrivial section as a top-down narrative that introduces its purpose before its implementation.
- Keep explanations next to the code they govern. Document intent, invariants, lifecycle, compatibility constraints, failure behavior, and non-obvious tradeoffs rather than restating syntax.
- Document public entry points and divide multi-phase scripts or validators into named conceptual phases. Prefer clear names and simple code over comments that compensate for avoidable complexity.
- Remove dead code instead of preserving it in comments. Keep every comment accurate when behavior changes, and update related maintainer documentation when workflows, package layout, supported versions, or validation rules change.
- Do not add narrative comments to generated files, dependency lockfiles, binaries, artwork, vendored content, or checksum-frozen recovered artifacts. Document those files in the maintained source that produces, validates, or consumes them instead.

## Validation Workflow

- Run `scripts/test.sh` for host-independent source, archive, extraction, and
  workflow contract tests.
- Run `scripts/build.sh` for maintained gameplay or package changes. It compiles
  the active 1.6 assembly, verifies the frozen 1.5 hashes, assembles the package,
  and validates its structure and localization coverage.
- Run `scripts/install-local.sh` after gameplay changes to build, validate, and
  transactionally install the current source package for development testing.
- The user performs one representative RimWorld smoke test: build a Void Shelf,
  select an intentional storage filter, haul a permitted item to it, and confirm
  the item is permanently destroyed on a rare tick.
- Do not merge a release-bearing pull request until the user confirms that the
  exact release candidate, rather than a later rebuild, passed its smoke test.
  Record the archive checksum and confirmation in the release record and pull
  request. Do not expand this into exhaustive QA without request.
- Documentation-only and process-only changes require only affected validation.
  Keep validation local; do not add hosted CI unless policy changes.

## Git Workflow (Build Mode)

- `main` is protected and must never receive direct commits or pushes. All changes go through feature branches.
- When making changes in build mode:
  1. Create a branch from `main` with a conventional prefix: `feat/`, `fix/`, `chore/`, `refactor/`, or `docs/` followed by a short kebab-case description (e.g. `feat/add-arch-gaming`).
  2. Determine whether the change is release-bearing. If it is, select the next
     version under `docs/RELEASES.md`, update `About/About.xml`, and add the
     matching release record on the same branch.
  3. Make the changes and run the appropriate validation. Release-bearing work
     must also complete the candidate workflow in `docs/RELEASES.md`.
  4. After validation passes, stage only intended files and commit with a
     [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
     message.
  5. Push the branch with `git push -u origin <branch-name>`.
  6. Create a pull request whose body includes a summary and validation results.
     Use a draft PR while a release-bearing change awaits candidate acceptance.
- If changes are requested, reuse the existing branch, validate, commit, and
  push. Do not create a replacement branch or PR.
- After exact-candidate smoke-test confirmation, update the release record and PR
  body, mark the PR ready, then ask: "Ready to merge, or need additional changes?"
- Before merging, inspect the clean worktree, every PR commit, and the complete
  diff from `main`. No hosted checks are expected.
- If the user confirms merge, merge with `gh pr merge --merge --delete-branch`,
  synchronize local `main`, delete the local branch, and prune the remote.
- This workflow applies to every change, including updates to `AGENTS.md` itself.

## Release Workflow

- Keep releases local and operator-driven. `docs/RELEASES.md` is authoritative
  for candidate acceptance and publication.
- Increment `modVersion` exactly once from the latest published version. Use
  PATCH for compatible fixes, MINOR for backward-compatible functionality, and
  MAJOR for intentional compatibility breaks.
- Record exact RimWorld, source, .NET SDK, Python, compression-tool, archive, and
  checksum details in the candidate record. Also record the frozen 1.5 hashes.
- From a clean candidate commit, run `python3 scripts/package-release.py`. It
  validates source, builds the package, writes the deterministic versioned ZIP
  and SHA-256 sidecar under `artifacts/releases/`, and refuses to replace
  different bytes for the same version.
- Run `scripts/install-local.sh --release` to verify the checksum, safely extract,
  validate, and transactionally install that exact archive without rebuilding.
  Then complete the representative smoke test and candidate record.
- After acceptance and merge, synchronize clean `main`, reproduce the archive,
  and require its checksum to match the tested candidate. A mismatch requires
  installing and smoke-testing the final archive again.
- Merge approval for an accepted release-bearing PR also authorizes its
  post-merge annotated tag and GitHub release unless checksum verification fails.
- Publish the installable ZIP, checksum, and release record. GitHub-generated
  source archives are repository snapshots, not installable RimWorld packages.
- Workshop publication remains a separate explicit step. Preserve recovered
  Workshop ID `3008773339`; never overwrite it as part of GitHub publication.
