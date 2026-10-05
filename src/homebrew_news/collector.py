import datetime
import os
import pathlib
import shutil
import subprocess
import typing

import stamina

from .digest import PackageChange


@typing.final
class GitCommandError(RuntimeError):
    """Git could not read or download a repository."""


def execute_git(repository_path: pathlib.Path | None, *arguments: str, timeout_seconds: int = 120) -> str:
    git_command: typing.Final = ["git"]
    if repository_path is not None:
        git_command.extend(["-C", str(repository_path)])
    git_command.extend(arguments)
    environment: typing.Final = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
    try:
        completed_process: typing.Final = subprocess.run(  # noqa: S603
            git_command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise GitCommandError(f"Could not run Git: {failure}") from failure
    if completed_process.returncode:
        raise GitCommandError(completed_process.stderr.strip() or "Git command failed")
    return completed_process.stdout


@stamina.retry(on=GitCommandError, attempts=3, wait_initial=1, wait_max=5)
def clone_repository(
    tap_name: str,
    destination_path: pathlib.Path,
    digest_date: datetime.date | None = None,
) -> None:
    # Each attempt gets a fresh destination, since failed clones may leave files behind.
    if destination_path.exists():
        shutil.rmtree(destination_path)
    execute_git(
        None,
        "clone",
        "--bare",
        "--filter=blob:none",
        "--single-branch",
        "--no-tags",
        *(["--depth=256"] if digest_date is not None else []),
        "--",
        f"https://github.com/{tap_name}.git",
        str(destination_path),
        timeout_seconds=300,
    )
    if digest_date is not None:
        for history_depth in (256, 512, 1024, 2048, 4096, 8192, 16384, 32768):
            if check_history_coverage(destination_path, digest_date):
                return
            execute_git(
                destination_path,
                "fetch",
                f"--deepen={history_depth}",
                "--filter=blob:none",
                "--no-tags",
                "origin",
                timeout_seconds=300,
            )
        if not check_history_coverage(destination_path, digest_date):
            raise GitCommandError("Requested day exceeds the remote history limit; use a full local checkout.")


def check_history_coverage(repository_path: pathlib.Path, digest_date: datetime.date) -> bool:
    if execute_git(repository_path, "rev-parse", "--is-shallow-repository").strip() != "true":
        return True
    shallow_location: typing.Final = execute_git(repository_path, "rev-parse", "--git-path", "shallow").strip()
    shallow_path: typing.Final = repository_path / shallow_location
    boundary_hashes: typing.Final = set(shallow_path.read_text(encoding="utf-8").splitlines())
    first_parent_history: typing.Final = execute_git(repository_path, "log", "--first-parent", "--format=%H%x09%ct")
    oldest_hash, oldest_timestamp = first_parent_history.splitlines()[-1].split("\t")
    period_start: typing.Final = datetime.datetime.combine(digest_date, datetime.time(), datetime.UTC)
    return oldest_hash not in boundary_hashes or int(oldest_timestamp) < period_start.timestamp()


def classify_package(package_path: str) -> typing.Literal["Formula", "Cask"] | None:
    parsed_path: typing.Final = pathlib.PurePosixPath(package_path)
    if parsed_path.suffix != ".rb":
        return None
    if parsed_path.parts[0] == "Casks" and len(parsed_path.parts) > 1:
        return "Cask"
    if len(parsed_path.parts) == 1 or parsed_path.parts[0] in {"Formula", "HomebrewFormula"}:
        return "Formula"
    return None


def collect_changes(
    repository_path: pathlib.Path,
    digest_date: datetime.date,
    *,
    allow_shallow: bool = False,
) -> tuple[PackageChange, ...]:
    if execute_git(repository_path, "rev-parse", "--is-shallow-repository").strip() == "true" and (
        not allow_shallow or not check_history_coverage(repository_path, digest_date)
    ):
        raise GitCommandError("A shallow local repository may omit changes; run git fetch --unshallow first.")
    period_start: typing.Final = datetime.datetime.combine(digest_date, datetime.time(), datetime.UTC)
    period_finish: typing.Final = period_start + datetime.timedelta(days=1)
    history_output: typing.Final = execute_git(
        repository_path,
        "log",
        "--first-parent",
        f"--since-as-filter={period_start.isoformat()}",
        f"--until={period_finish.isoformat()}",
        "--format=%H%x09%ct%x09%s",
        "HEAD",
        "--",
    )
    package_changes: typing.Final[list[PackageChange]] = []
    for history_line in history_output.splitlines():
        commit_hash, timestamp_text, commit_subject = history_line.split("\t", 2)
        committed_at = datetime.datetime.fromtimestamp(int(timestamp_text), datetime.UTC)
        if not period_start <= committed_at < period_finish:
            continue
        parent_hashes = execute_git(repository_path, "rev-list", "--parents", "-n", "1", commit_hash).split()
        comparison_hashes = [*parent_hashes[1:2], commit_hash]
        changed_paths = execute_git(
            repository_path,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "-r",
            "--no-renames",
            "--name-status",
            "-z",
            *comparison_hashes,
            "--",
        ).split("\0")
        for status_code, package_path in zip(changed_paths[0:-1:2], changed_paths[1:-1:2], strict=True):
            package_kind = classify_package(package_path)
            if package_kind is None or status_code not in {"A", "M", "D", "T"}:
                continue
            change_kind: typing.Literal["Added", "Updated", "Removed"] = (
                "Added" if status_code == "A" else "Removed" if status_code == "D" else "Updated"
            )
            package_changes.append(
                PackageChange(
                    package_name=pathlib.PurePosixPath(package_path).stem,
                    package_kind=package_kind,
                    change_kind=change_kind,
                    commit_hash=commit_hash,
                    commit_subject=commit_subject,
                    package_path=package_path,
                )
            )
    return tuple(
        sorted(package_changes, key=lambda change: (change.package_kind, change.package_name, change.commit_hash))
    )
