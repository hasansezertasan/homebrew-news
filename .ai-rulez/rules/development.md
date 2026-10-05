---
name: development
description: Development and verification conventions for homebrew-news.
---

Use Python 3.12+ and uv with the checked-in lockfile. Keep the collector independent
of Hermes; share collection behavior between the CLI and the plugin through
`src/homebrew_news/service.py`. Match the existing typing and Ruff conventions.

Read Git history without executing Ruby package definitions. Interpret updated
files as file changes unless version evidence is explicit. Preserve UTC day
boundaries, full counts, truncation flags, source links, and partial failures.

Plugin registration must perform no network access, create no schedules, and write
no state. Use Hermes profile state during collection. Keep dependencies and settings
declared in the native plugin's packaging and manifest.

Run `make check` for CI parity: version consistency, generated-output verification,
linting, formatting, strict type checks, offline tests, and package builds.
Tests use temporary local Git repositories; do not depend on live Homebrew history.

Edit contributor guidance in `.ai-rulez/` and the runtime news skill in
`src/homebrew_news/skills/write-news/SKILL.md`, then run `make generate`.
Never hand-edit generated outputs. Release-please owns release version bumps;
its workflow refreshes the lockfile and regenerates plugin artifacts on its PR.
Use Conventional Branch names and Conventional Commits for commits and PR titles.
