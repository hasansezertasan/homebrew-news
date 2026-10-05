import datetime
import os
import pathlib
import subprocess
import sys
import typing

import pytest
import stamina

from homebrew_news import collector
from homebrew_news.cli import run_cli
from homebrew_news.collector import GitCommandError, HistoryLimitError, collect_changes
from homebrew_news.config import load_configuration
from homebrew_news.digest import render_digest


def run_git_command(repository_path: pathlib.Path, *arguments: str, committed_at: str = "2026-10-04T12:00:00Z") -> str:
    environment: typing.Final = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_DATE": "2026-01-01T12:00:00Z",
        "GIT_COMMITTER_DATE": committed_at,
    }
    return subprocess.run(
        ["git", "-C", str(repository_path), *arguments],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository_path(tmp_path: pathlib.Path) -> pathlib.Path:
    run_git_command(tmp_path, "init", "-b", "main")
    run_git_command(tmp_path, "config", "user.name", "Test Author")
    run_git_command(tmp_path, "config", "user.email", "author@example.com")
    run_git_command(tmp_path, "config", "commit.gpgsign", "false")
    run_git_command(tmp_path, "config", "core.hooksPath", os.devnull)
    return tmp_path


def commit_package(
    repository_path: pathlib.Path,
    package_path: str,
    package_text: str,
    commit_subject: str,
    committed_at: str = "2026-10-04T12:00:00Z",
) -> None:
    target_path: typing.Final = repository_path / package_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(package_text, encoding="utf-8")
    run_git_command(repository_path, "add", "--", package_path)
    run_git_command(repository_path, "commit", "-m", commit_subject, committed_at=committed_at)


def test_collects_changes_at_utc_boundaries(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/old.rb", "old", "Before day", "2026-10-03T23:59:59Z")
    commit_package(repository_path, "Formula/a/new.rb", "v1", "New formula", "2026-10-04T03:00:00+03:00")
    commit_package(repository_path, "Casks/b/browser.rb", "v1", "New cask")
    commit_package(repository_path, "Casks/b/browser.rb", "v2", "Browser [update](https://example.com)")
    run_git_command(repository_path, "rm", "Formula/old.rb")
    run_git_command(repository_path, "commit", "-m", "Remove old")
    commit_package(repository_path, "README.md", "documentation", "Docs only")
    commit_package(repository_path, "scripts/helper.rb", "script", "Internal tooling")
    commit_package(repository_path, "Formula/tomorrow.rb", "v1", "Tomorrow", "2026-10-05T00:00:00Z")

    package_changes: typing.Final = collect_changes(repository_path, datetime.date(2026, 10, 4))
    digest_markdown: typing.Final = render_digest("example/homebrew-tap", datetime.date(2026, 10, 4), package_changes)

    assert {(change.package_name, change.change_kind) for change in package_changes} == {
        ("new", "Added"),
        ("browser", "Added"),
        ("browser", "Updated"),
        ("old", "Removed"),
    }
    assert "4 package file changes." in digest_markdown
    assert "Browser \\[update\\]\\(https://example.com\\)" in digest_markdown
    assert "https://github.com/example/homebrew-tap/commit/" in digest_markdown
    assert digest_markdown == render_digest("example/homebrew-tap", datetime.date(2026, 10, 4), package_changes)


@pytest.mark.parametrize(
    "package_path", ["root.rb", "HomebrewFormula/legacy.rb", "Formula/f/formula.rb", "Casks/c/cask.rb"]
)
def test_collects_root_commit(repository_path: pathlib.Path, package_path: str) -> None:
    commit_package(repository_path, package_path, "definition", "First package")

    package_changes: typing.Final = collect_changes(repository_path, datetime.date(2026, 10, 4))

    assert len(package_changes) == 1
    assert package_changes[0].change_kind == "Added"
    assert package_changes[0].package_path == package_path


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085", "\r", "\t"])
def test_collects_subjects_with_line_separators(repository_path: pathlib.Path, separator: str) -> None:
    commit_subject: typing.Final = f"Add{separator}tool"
    commit_package(repository_path, "Formula/tool.rb", "v1", commit_subject)
    commit_package(repository_path, "Formula/other.rb", "v1", "Add other")

    package_changes: typing.Final = collect_changes(repository_path, datetime.date(2026, 10, 4))

    assert {change.package_name: change.commit_subject for change in package_changes} == {
        "tool": commit_subject.replace("\r", "\n"),
        "other": "Add other",
    }


def test_reports_merge_once(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "README.md", "base", "Initial", "2026-10-03T00:00:00Z")
    run_git_command(repository_path, "checkout", "-b", "feature")
    commit_package(repository_path, "Formula/merged.rb", "v1", "Branch addition", "2026-10-03T12:00:00Z")
    run_git_command(repository_path, "checkout", "main")
    run_git_command(repository_path, "merge", "--no-ff", "feature", "-m", "Merge package")

    package_changes: typing.Final = collect_changes(repository_path, datetime.date(2026, 10, 4))

    assert len(package_changes) == 1
    assert package_changes[0].package_name == "merged"
    assert package_changes[0].commit_subject == "Merge package"


def test_does_not_prune_history_after_backdated_commit(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/recent.rb", "v1", "Inside day")
    commit_package(repository_path, "README.md", "backdated", "Older timestamp", "2026-10-01T00:00:00Z")

    package_changes: typing.Final = collect_changes(repository_path, datetime.date(2026, 10, 4))

    assert [change.package_name for change in package_changes] == ["recent"]


def test_cli_writes_digest_file(repository_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Add tool")
    output_path: typing.Final = tmp_path / "digests" / "news.md"

    completed_process: typing.Final = subprocess.run(
        [
            sys.executable,
            "-m",
            "homebrew_news",
            "--tap",
            "example/homebrew-tap",
            "--repository",
            str(repository_path),
            "--date",
            "2026-10-04",
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout == ""
    assert "**tool** (Formula)" in output_path.read_text(encoding="utf-8")


def test_quiet_day_outputs_markdown(repository_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    commit_package(repository_path, "README.md", "docs", "Docs only")

    exit_status: typing.Final = run_cli(
        [
            "--tap",
            "example/homebrew-tap",
            "--repository",
            str(repository_path),
            "--date",
            "2026-10-04",
        ]
    )

    assert exit_status == 0
    assert "No formula or cask changes" in capsys.readouterr().out


@pytest.mark.parametrize(
    "invalid_arguments",
    [
        ["--tap", "../bad"],
        ["--tap", "example/homebrew-tap", "--date", "2026-02-30"],
        ["--tap", "example/homebrew-tap", "--date", "20261004"],
        ["--tap", "example/homebrew-tap", "--date", "9999-12-31"],
    ],
)
def test_rejects_invalid_arguments(invalid_arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as captured_failure:
        run_cli(invalid_arguments)
    assert captured_failure.value.code == 2


def test_invalid_repository_returns_error(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_status: typing.Final = run_cli(["--tap", "example/homebrew-tap", "--repository", str(tmp_path)])

    assert exit_status == 1
    assert "homebrew-news:" in capsys.readouterr().err


def test_rejects_shallow_history(repository_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Initial")
    shallow_path: typing.Final = tmp_path / "shallow"
    run_git_command(tmp_path, "clone", "--depth", "1", repository_path.as_uri(), str(shallow_path))

    with pytest.raises(GitCommandError, match="shallow"):
        collect_changes(shallow_path, datetime.date(2026, 10, 4))


def test_config_groups_successful_taps_and_reports_failure(
    repository_path: pathlib.Path,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Add tool")
    second_path: typing.Final = tmp_path / "second"
    second_path.mkdir()
    run_git_command(second_path, "clone", str(repository_path), ".")
    config_path: typing.Final = tmp_path / "taps.toml"
    config_path.write_text(
        '[[taps]]\nrepository = "example/first"\npath = "."\n'
        '[[taps]]\nrepository = "example/missing"\npath = "missing"\n'
        '[[taps]]\nrepository = "example/second"\npath = "second"\n',
        encoding="utf-8",
    )
    output_path: typing.Final = tmp_path / "digest.md"

    exit_status: typing.Final = run_cli(
        [
            "--config",
            str(config_path),
            "--date",
            "2026-10-04",
            "--output",
            str(output_path),
        ]
    )
    digest_text: typing.Final = output_path.read_text(encoding="utf-8")

    assert exit_status == 1
    assert "3 taps tracked; 1 failed" in digest_text
    assert "**Partial digest:**" in digest_text
    assert "## [example/first]" in digest_text
    assert "## [example/second]" in digest_text
    assert "### Added" in digest_text
    assert digest_text.count("**tool**") == 2
    assert "Collection failed:" in digest_text
    assert "example/missing:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "config_text",
    [
        "",
        "taps = []",
        'taps = ["example/tap"]',
        "[[taps]]\nrepository = 123",
        '[[taps]]\nrepository = "../bad"',
        '[[taps]]\nrepository = "example/tap"\npath = 123',
        '[[taps]]\nrepository = "example/tap"\npath = ""',
        '[[taps]]\nrepository = "example/tap"\nextra = "typo"',
        '[[taps]]\nrepository = "example/tap"\n[[taps]]\nrepository = "EXAMPLE/TAP"',
        'other = true\n[[taps]]\nrepository = "example/tap"',
    ],
)
def test_rejects_invalid_configuration(tmp_path: pathlib.Path, config_text: str) -> None:
    config_path: typing.Final = tmp_path / "taps.toml"
    config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(ValueError, match=r".+"):
        load_configuration(config_path)


def test_defaults_to_configuration(
    repository_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    commit_package(repository_path, "README.md", "base", "Docs")
    config_path: typing.Final = repository_path / "taps.toml"
    config_path.write_text('[[taps]]\nrepository = "example/tap"\npath = "."', encoding="utf-8")
    monkeypatch.chdir(repository_path)

    exit_status: typing.Final = run_cli(["--date", "2026-10-04"])

    assert exit_status == 0
    assert "1 tap tracked; 0 failed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "cli_arguments",
    [
        ["--repository", "."],
        ["--config", "missing.toml"],
        ["--tap", "example/tap", "--config", "taps.toml"],
    ],
)
def test_rejects_invalid_source_arguments(cli_arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as captured_failure:
        run_cli(cli_arguments)
    assert captured_failure.value.code == 2


def test_bounded_remote_history_requires_parent_before_day(
    repository_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    commit_package(repository_path, "README.md", "base", "Root", "2026-10-02T12:00:00Z")
    commit_package(repository_path, "Formula/tool.rb", "v1", "Old addition", "2026-10-03T12:00:00Z")
    commit_package(repository_path, "Formula/tool.rb", "v2", "Update tool")
    shallow_path: typing.Final = tmp_path / "bounded"
    run_git_command(tmp_path, "clone", "--depth", "1", repository_path.as_uri(), str(shallow_path))

    with pytest.raises(GitCommandError, match="shallow"):
        collect_changes(shallow_path, datetime.date(2026, 10, 4), allow_shallow=True)

    run_git_command(shallow_path, "fetch", "--deepen", "1")
    package_changes: typing.Final = collect_changes(shallow_path, datetime.date(2026, 10, 4), allow_shallow=True)

    assert len(package_changes) == 1
    assert package_changes[0].change_kind == "Updated"


def test_history_limit_is_not_retried(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_calls: typing.Final[list[tuple[str, ...]]] = []

    def record_git(_repository_path: pathlib.Path | None, *arguments: str, timeout_seconds: int = 120) -> str:
        del timeout_seconds
        git_calls.append(arguments)
        return ""

    monkeypatch.setattr(collector, "execute_git", record_git)
    monkeypatch.setattr(collector, "check_history_coverage", lambda *_: False)
    stamina.set_testing(True, attempts=3)
    try:
        with pytest.raises(HistoryLimitError):
            collector.clone_repository("example/homebrew-tap", tmp_path / "tap.git", datetime.date(2000, 1, 1))
    finally:
        stamina.set_testing(False)

    assert sum(arguments[0] == "clone" for arguments in git_calls) == 1
