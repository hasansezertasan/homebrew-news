<!--
🤖 AI-RULEZ :: GENERATED FILE — DO NOT EDIT
Project: homebrew-news
Source: .ai-rulez/config.toml

NEVER edit this file - modify .ai-rulez/ content instead
Use MCP server: npx -y ai-rulez@latest mcp
Regenerate: ai-rulez generate

Docs: https://github.com/Goldziher/ai-rulez
Content-Hash: blake3:393bdd881718df434b06f8c1dc1754223733652d93dc58953c22ee28867d3364
Source-Hash: blake3:d47ae3872d47a06b38af95ce618c45bfb2bb382aaaad947b7b22cbd4b8f92b12
-->

# homebrew-news

A Hermes plugin and Python CLI for sourced Homebrew tap news.

## Context

### architecture

`src/homebrew_news/` contains the collector, configuration, digest rendering,
shared service, CLI, and Hermes tool. `taps.toml` defaults to Homebrew/homebrew-core.
The package's `plugin.yaml` and `__init__.py` support native Git-subdirectory and
directory installation; the repository root is not a Python package.
`pyproject.toml` also exposes the CLI and Hermes Python entry point.

AI Rulez generates contributor instructions for Codex, Claude, and Hermes, plus
Hermes adapter bundles under `.hermes/`. The adapter delegates to the installed
`homebrew_news` package. AI Rulez 4.24.2 does not include implementation dependencies,
manifest v2 tool declarations, or the settings schema in those bundles. The native
`src/homebrew_news/` plugin and main Python wheel remain the supported distribution artifacts.
Do not replace their manifest or packaging with the generated basic metadata.

The runtime skill stays in the Python package and is copied into generated bundles
using `plugin.content_root`; developer rules are never bundled as runtime skills.
GitHub Actions checks quality and generated output consistency. Hermes cron owns
digest scheduling; there is no daily digest GitHub workflow.

`Makefile` provides the shared local/CI entry point. `scripts/check_repository.py`
checks version copies, native/wheel dependency agreement, and regeneration in a temporary tree. Release-please uses
the Python strategy and extra-file updates for the native manifest and AI Rulez
source version; the release workflow refreshes the lockfile and generated outputs.
See `.github/CONTRIBUTING.md` for release setup and recovery.
