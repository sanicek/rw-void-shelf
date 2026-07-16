# AGENTS.md

## Literate Programming

- Write all maintained code in a literate programming style: present each file and nontrivial section as a top-down narrative that introduces its purpose before its implementation.
- Keep explanations next to the code they govern. Document intent, invariants, lifecycle, compatibility constraints, failure behavior, and non-obvious tradeoffs rather than restating syntax.
- Document public entry points and divide multi-phase scripts or validators into named conceptual phases. Prefer clear names and simple code over comments that compensate for avoidable complexity.
- Remove dead code instead of preserving it in comments. Keep every comment accurate when behavior changes, and update related maintainer documentation when workflows, package layout, supported versions, or validation rules change.
- Do not add narrative comments to generated files, dependency lockfiles, binaries, artwork, vendored content, or checksum-frozen recovered artifacts. Document those files in the maintained source that produces, validates, or consumes them instead.

## Git Workflow (Build Mode)

- `main` is protected and must never receive direct commits or pushes. All changes go through feature branches.
- When making changes in build mode:
  1. Create a branch from `main` with a conventional prefix: `feat/`, `fix/`, `chore/`, `refactor/`, or `docs/` followed by a short kebab-case description (e.g. `feat/add-arch-gaming`).
  2. Make the changes.
  3. Run the appropriate validation.
  4. After validation passes, stage the changed files and commit with a [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) message (`feat(scope): description`, `fix: description`, `chore: description`, `docs: description`, etc.).
  5. Push the branch with `git push -u origin <branch-name>`.
  6. Create a pull request with `gh pr create --title "..." --body "..."`. The body must include a summary of what changed and which validation was run.
- After creating the PR, ask the user for confirmation ("Ready to merge, or need additional changes?").
  - If the user requests changes, reuse the existing feature branch (do not create a new one). Make the changes, validate, commit, and push; the PR updates automatically, then ask again.
  - If the user confirms merge, merge the PR with `gh pr merge --merge --delete-branch`, then clean up locally: `git checkout main`, `git pull origin main`, `git branch -d <branch-name>`, and `git remote prune origin`.
- This workflow applies to every change, including updates to `AGENTS.md` itself.
