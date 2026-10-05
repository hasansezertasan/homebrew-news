<!--
🤖 AI-RULEZ :: GENERATED FILE — DO NOT EDIT
Project: homebrew-news
Source: .ai-rulez/config.toml

NEVER edit this file - modify .ai-rulez/ content instead
Use MCP server: npx -y ai-rulez@latest mcp
Regenerate: ai-rulez generate

Docs: https://github.com/Goldziher/ai-rulez
Content-Hash: blake3:5f97f04f29eb8f2b17c2353a23feae56ab64f9d33548d58d6499585ed2d3ca73
Source-Hash: blake3:97154d97f7adf1b6ef30b06f6be8d6e788786d82c8277d622a4fbdd04849be2e
-->

# homebrew-news

A Hermes plugin and Python CLI for sourced Homebrew tap news.

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
