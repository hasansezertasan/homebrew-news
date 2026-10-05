# homebrew-news

A native [Hermes Agent](https://hermes-agent.nousresearch.com/) plugin for Homebrew
tap news. Collect formula and cask changes, return structured evidence and Markdown,
and let Hermes write a sourced daily summary. The default tap is
[Homebrew/homebrew-core](https://github.com/Homebrew/homebrew-core).

The same collector is available as a standalone Python CLI.

## Use with Hermes

Requirements: current Hermes Agent, Python 3.12+, and Git 2.37+. Install from Git
after these changes are published:

```sh
hermes plugins install 'hasansezertasan/homebrew-news#src/homebrew_news' --enable
```

Hermes asks for consent to prepare the declared Python dependency (`stamina`)
before enabling the plugin. Restart an existing session or gateway after enabling
to make the tool available. Check installation with `hermes plugins list`.

For local development, copy the contents of `src/homebrew_news/` into
`~/.hermes/plugins/homebrew-news/` (excluding `__pycache__`), then run
`hermes plugins enable homebrew-news`. Hermes prepares declared
dependencies as part of enablement. The Python package also exposes a
`hermes_agent.plugins` entry point for pip installations into Hermes's runtime.
A separate `uv tool install` installs only the standalone CLI, not a Hermes plugin.

Ask Hermes:

> Load the homebrew-news:write-news skill and summarize yesterday's Homebrew news.

Or call `homebrew_news_digest` with:

```json
{"date": "2026-10-04", "limit": 100}
```

`date` defaults to yesterday UTC. Optional `tap` overrides the configured list for
one call. `limit` defaults to 50 detailed file changes **per tap**, with a maximum
of 200. The JSON result includes `status` (`ok`, `partial`, or `error`), per-tap
full counts, source commit URLs, bounded change lists, truncation flags, and Markdown.
Full counts include entries omitted by the detail limit. Use the CLI for complete
exports. Quiet days and collection failures are distinct outcomes.

The tool gathers evidence; Hermes uses the bundled `homebrew-news:write-news` skill
to write the final news. Updated files are not automatically version upgrades.
The skill describes how to preserve links, counts, partial failures, and limits.

### Hermes settings

Configure these keys in your active Hermes profile's `config.yaml`:

```yaml
plugins:
  entries:
    homebrew-news:
      settings:
        taps:
          - Homebrew/homebrew-core
        config_path: ''
```

`taps` defaults to `[Homebrew/homebrew-core]`. An optional `config_path` overrides
that list with a `taps.toml` file, using the same format as the CLI. Native directory
plugins resolve relative paths against their installation directory; for pip
installations, use an absolute path. Local checkout paths inside TOML are relative
to that file. Settings are read on each tool call, not cached at startup.

Successful collections save small `last_collection` metadata through Hermes's
profile-scoped `ctx.state`: the UTC day, collection timestamp, and successful and
failed taps. No runtime files are written into the plugin's installation tree.
This metadata does not suppress reruns or automatically backfill missed days.

### Schedule news in Hermes

To create a daily agent job that produces news and saves it locally:

```sh
hermes cron create '17 2 * * *' \
  'Use homebrew_news_digest for yesterday UTC and write a sourced Homebrew news summary. Report failed taps and truncated results.' \
  --skill homebrew-news:write-news \
  --name homebrew-news \
  --deliver local
```

Check the scheduler's configured timezone before choosing a cron expression.
The Hermes gateway must remain running to execute jobs. Choose a configured
delivery destination if you want news in a chat rather than local output. See
[Hermes scheduling](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron).
Installation and registration do not create jobs, enable a gateway, or send messages.

## MVP

- Track a configurable list of taps, using full GitHub `owner/repository` names.
- Expose a Hermes tool, namespaced news-writing skill, and profile-scoped collection metadata.
- Collect added, updated, and removed package files for a UTC calendar day.
- Group changes by tap into readable Markdown with package names, commit subjects, and
  links to the source commits.
- Print to stdout or save a file for publishing elsewhere.
- Support local repositories for offline use and reproducible tests.
- Schedule daily summaries and delivery through Hermes's cron tools.

This implementation reads Git history; it does not install packages or execute
Ruby definitions. A website, RSS, and public feed publishing are future work.

## Quick start

Requirements: Python 3.12+, Git 2.37+, and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run homebrew-news --output digests/daily.md
```

The default day is **yesterday in UTC**. Select a day and save its digest:

```sh
uv run homebrew-news \
  --config taps.toml \
  --date 2026-10-04 \
  --output digests/2026-10-04.md
```

Use an existing checkout without network access:

```sh
uv run homebrew-news \
  --tap owner/homebrew-tap \
  --repository /path/to/homebrew-tap \
  --date 2026-10-04
```

### Tap configuration

With no `--tap`, the CLI reads `taps.toml` from the current directory. The checked-in
configuration tracks [Homebrew/homebrew-core](https://github.com/Homebrew/homebrew-core).
Add repositories as separate tables:

```toml
[[taps]]
repository = "Homebrew/homebrew-core"

[[taps]]
repository = "owner/homebrew-tap"
# Optional local checkout, resolved relative to this configuration file:
# path = "../homebrew-tap"
```

Use `--config /path/to/taps.toml` to select another file, or
`--tap Homebrew/homebrew-core` to bypass configuration and track just one tap.
`--tap` and `--config` are mutually exclusive. `--repository` requires `--tap`;
use per-tap `path` fields for local repositories in a configuration file.
Empty lists, duplicate repositories, unknown fields, and invalid names are rejected.

If a tap fails, collection continues for the remaining taps. The output is marked
as partial and includes the failed tap's error rather than claiming it had no
changes. The CLI saves the digest and exits with status 1 if any tap failed.

The local option reads `HEAD` as it stands and does not fetch updates. Use a full
checkout: shallow repositories are rejected because they can omit changes or
misreport the oldest commit as additions. `--tap` controls the source links, so
it must match the checkout's GitHub repository. Use the full repository name
(`owner/homebrew-tap`), rather than Homebrew's shorthand (`owner/tap`).

You can also install the CLI with `uv tool install .`, or invoke it with
`uv run python -m homebrew_news`.

## Digest semantics

The interval is `[00:00 UTC, next day 00:00 UTC)`, based on **committer dates**.
Remote runs clone the default branch into a temporary bare repository and delete
it afterward. They start with 256 commits and deepen history until the first-parent
shallow boundary is older than the requested day, so the oldest fetched commit
is never mistaken for a new package. Blob filtering avoids downloading Ruby file
contents. Remote clones and fetches have a five-minute timeout; other Git commands
have a two-minute timeout. Clone failures are retried up to three times. Git
authentication prompts are disabled; this MVP targets public GitHub taps.
Remote history deepening is capped at approximately 65,000 commits. For older
dates, use a full local checkout. The remote boundary check assumes older omitted
history has older timestamps; use a full local checkout if a tap has unusual
backdated commits. Repository caches are not yet persisted between runs.

First-parent traversal reports merged changes once, at the merge commit. Each
commit is compared with its first parent. Package files are `.rb` files under
`Formula/`, `HomebrewFormula/`, `Casks/`, or the repository root, including nested
directories. These locations follow Homebrew's
[tap layout](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap).
Other files are ignored.

“Updated” means the package file changed. This includes version bumps, rebuilds,
metadata edits, and other maintenance; the MVP does not parse Ruby or infer
version numbers. Renames appear as a removal and an addition. A package changed
in several commits gets several entries, so the count measures file changes
rather than unique packages. Entries are sorted by package kind, name, and commit
hash for deterministic output. A quiet day produces an explicit no-changes digest.

Invalid arguments or configuration exit with status 2; Git or filesystem failures
exit with status 1 and a message on stderr. Successful runs exit with status 0.

## Continuous integration

`.github/workflows/ci.yml` runs linting, formatting, strict type checks, offline
integration tests, AI Rulez validation and generated-output checks, and package
builds on pushes and pull requests with Python 3.12 and 3.13. The workflow uses
locked dependencies and read-only repository permissions.

### AI Rulez

[AI Rulez](https://github.com/Goldziher/ai-rulez) is pinned to 4.24.2 in the development
dependencies. `.ai-rulez/config.toml` generates contributor instructions for Codex
(`AGENTS.md`), Claude (`CLAUDE.md` and `.claude/rules/`), and Hermes (`.hermes.md`).
Edit the source rules and context under `.ai-rulez/`, not those generated files.

```sh
uv run ai-rulez validate
uv run ai-rulez generate --no-local
uv run ai-rulez generate --plugin --no-local
uv run ai-rulez verify --plugin
```

Plugin generation copies the canonical runtime skill from
`src/homebrew_news/skills/` and the adapter from `.ai-rulez/hermes/index.py` into
`.hermes/plugins/homebrew-news/` and a Python adapter package in `.hermes/package/`.
Generated artifacts and their provenance file are committed and checked in CI.
`--no-local` keeps regeneration independent of personal AI Rulez overrides.

These generated adapters require `homebrew_news` to be importable in the Hermes
runtime. AI Rulez 4.24.2 does not declare that dependency or preserve our manifest
v2 tool declarations and settings schema. Use the native `src/homebrew_news/` plugin or the main
Python wheel for installation as described above; the generated adapter package
is not a standalone replacement. It can be built for integration development with
`uv build .hermes/package --out-dir dist/hermes`.

## Development

```sh
uv sync
make check

# After changing AI Rulez source content:
make generate

# With Hermes installed; registration validation does not collect news:
hermes plugins doctor src/homebrew_news --ci
hermes plugins validate src/homebrew_news
```

Tests create temporary Git repositories and exercise the CLI without network
access, including UTC boundaries, root commits, merges, removals, and output files.
Plugin tests invoke the registered handler, native directory entry point, and both
AI Rulez adapter entry points,
including malformed arguments, bounded output, partial results, and state failures.
The bundled skill and typing marker are included in the wheel.

The native manifest lives at `src/homebrew_news/plugin.yaml`, beside the package's
`__init__.py` registration entry point and runtime skill. Hermes installs this Git
subdirectory as the plugin, so its relative imports work without adding `src/`
to global `sys.path` or making the repository root a Python package.
The manifest declares dependencies for directory installation; `pyproject.toml`
declares the same dependencies for the wheel. Hermes prepares directory-plugin
dependencies through its normal admission process.
Registration performs no network access or state writes. See the
[Hermes plugin contract](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins).

Release-please maintains release PRs, synchronized versions, and the changelog.
Renovate schedules weekly dependency updates. See
[Contributing](.github/CONTRIBUTING.md) for generated-file ownership, release behavior,
and the GitHub settings needed to activate these workflows.

## Next steps

1. Persist or reuse repository caches for repeated runs.
2. Generate RSS and publish digests on a website.
3. Extract version details when they can be determined reliably.
