<!--
🤖 AI-RULEZ :: GENERATED FILE — DO NOT EDIT
Project: homebrew-news
Source: .ai-rulez/config.toml

NEVER edit this file - modify .ai-rulez/ content instead
Use MCP server: npx -y ai-rulez@latest mcp
Regenerate: ai-rulez generate

Docs: https://github.com/Goldziher/ai-rulez
Content-Hash: blake3:7b6a4efb5488430fb1f02aabec8bc1d97ca9bb42647c93a0f5970e188d6f7551
Source-Hash: blake3:97154d97f7adf1b6ef30b06f6be8d6e788786d82c8277d622a4fbdd04849be2e
-->

# homebrew-news

A Hermes plugin and Python CLI for sourced Homebrew tap news.

## Rules

### development

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

## Context

### architecture

`src/homebrew_news/` contains the collector, configuration, digest rendering,
shared service, CLI, and Hermes tool. `taps.toml` defaults to Homebrew/homebrew-core.
Root `plugin.yaml` and `__init__.py` support native Git/directory installation;
`pyproject.toml` also exposes the CLI and Hermes Python entry point.

AI Rulez generates contributor instructions for Codex, Claude, and Hermes, plus
Hermes adapter bundles under `.hermes/`. The adapter delegates to the installed
`homebrew_news` package. AI Rulez 4.24.2 does not include implementation dependencies,
manifest v2 tool declarations, or the settings schema in those bundles. The root
native plugin and main Python wheel remain the supported distribution artifacts.
Do not replace their manifest or packaging with the generated basic metadata.

The runtime skill stays in the Python package and is copied into generated bundles
using `plugin.content_root`; developer rules are never bundled as runtime skills.
GitHub Actions checks quality and generated output consistency. Hermes cron owns
digest scheduling; there is no daily digest GitHub workflow.

`Makefile` provides the shared local/CI entry point. `scripts/check_repository.py`
checks version copies and regeneration in a temporary tree. Release-please uses
the Python strategy and extra-file updates for the native manifest and AI Rulez
source version; the release workflow refreshes the lockfile and generated outputs.
See `.github/CONTRIBUTING.md` for release setup and recovery.
