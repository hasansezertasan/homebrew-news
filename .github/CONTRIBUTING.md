# Contributing to homebrew-news

Run `make check` for the same validation, linting, type checks, offline integration
tests, and package builds that CI runs. It installs the locked uv development
dependencies. Python 3.14, uv, Git, and Make are required.
`.python-version` selects Python 3.14 for local uv commands.

With mise installed, install the pinned uv version and run the checks:

```sh
mise install
mise exec -- make check
```

## Sources and generated files

Edit `.ai-rulez/rules/` and `.ai-rulez/context/` for contributor guidance, and
`src/homebrew_news/skills/write-news/SKILL.md` for the runtime news skill.
The canonical Hermes adapter is `.ai-rulez/hermes/index.py`.
Run `make generate` after changing those sources or `.ai-rulez/config.toml`.

`AGENTS.md`, `CLAUDE.md`, `.claude/rules/`, `.hermes.md`, and `.hermes/` are generated.
`.ai-rulez/.generated-manifest.json` lists contributor outputs;
`.ai-rulez-generated.json` lists plugin outputs and their hashes.
The native `src/homebrew_news/plugin.yaml`, package `__init__.py`, and main Python
package are hand-authored. The native plugin's manifest dependencies must match
`pyproject.toml`; `make check` detects drift between the two installation forms.

`make check` compares versions and regenerates AI Rulez output into a temporary
directory, so it catches stale files without rewriting your checkout.

Use Conventional Branch names and Conventional Commit messages and PR titles.
Squash-merged PR titles determine release notes and version bumps.

## Releases

The release workflow uses release-please's Python strategy to maintain
`pyproject.toml`, `CHANGELOG.md`, and `.config/release-please-manifest.json`.
Its extra-file rules also update the native `src/homebrew_news/plugin.yaml` and
`.ai-rulez/config.toml` source version. The workflow refreshes `uv.lock`, runs
`make generate`, and checks the release PR before pushing its regenerated files.
Do not edit generated version copies by hand.

The manifest starts at the current development version as a bootstrap baseline;
it does not assert that a release already exists. The first release PR proposes
the next version from releasable Conventional Commits. `chore`, `test`, and `ci`
commits alone do not request a new release.

After a release PR merges into `main`, the workflow validates that merge commit
with the Python 3.14 CI checks before creating its `vX.Y.Z` tag and GitHub Release.
A later passing push cannot release an earlier pending merge that failed checks.
The tagged repository's `src/homebrew_news/` directory is the Hermes installation
artifact. The workflow does not
publish to PyPI or upload the generated adapter wheel as a standalone distribution.

### Repository setup

Enable **Settings → Actions → General → Allow GitHub Actions to create and approve
pull requests**. The workflow uses `GITHUB_TOKEN`; no publishing credential is needed.
Configure branch protection on `main` to require the `quality` CI check before merging,
and use squash merging so PR titles become the Conventional Commit messages.

GitHub does not normally trigger new workflows from pushes and PR events created
with `GITHUB_TOKEN`. After the generated commit lands on a release PR, run the CI
workflow manually on its branch, or push a maintainer commit to trigger PR checks
if your branch protection requires PR event checks. A GitHub App token can automate
those events later. The release workflow also runs `make check` before pushing the
generated commit and runs CI after the PR merges.

### Recovering a release

If the release workflow fails transiently, rerun the workflow for the release PR's
merge commit. A newer passing push deliberately does not create its release.

If that merge genuinely fails checks, merge the fix and validate it first.
A maintainer can then create the release on the fixed commit and change the old
PR's label from `autorelease: pending` to `autorelease: tagged`, so release-please
can proceed. If an older queued run was replaced by a newer push, rerun the release
merge's run after the queue clears.

## Dependency maintenance

Renovate uses native Python/uv and GitHub Actions managers, with weekly updates
and automerge disabled. Activate the Renovate app for the repository separately.
Keep Python tool versions in `pyproject.toml` and its lockfile, and the uv version
in `mise.toml`, which both workflows read. Renovate's native mise manager
updates that pin. No npm tooling or regex managers are needed.
GitHub Action pins live in their workflow `uses` fields.
