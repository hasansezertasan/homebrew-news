import argparse
import datetime
import pathlib
import sys
import tomllib
import typing

from .collector import GitCommandError
from .config import TapSettings, load_configuration, validate_tap_name
from .digest import render_digest, render_grouped_digest
from .service import collect_tap_digests


def parse_tap_name(argument: str) -> str:
    try:
        return validate_tap_name(argument)
    except ValueError as failure:
        raise argparse.ArgumentTypeError(str(failure)) from failure


def parse_digest_date(argument: str) -> datetime.date:
    try:
        parsed_date: typing.Final = datetime.date.fromisoformat(argument)
    except ValueError as failure:
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format.") from failure
    if argument != parsed_date.isoformat():
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format.")
    return parsed_date


def run_cli(arguments: typing.Sequence[str] | None = None) -> int:
    argument_parser: typing.Final = argparse.ArgumentParser(description="Generate a daily Homebrew tap digest.")
    source_arguments: typing.Final = argument_parser.add_mutually_exclusive_group()
    source_arguments.add_argument("--tap", type=parse_tap_name, help="Track one GitHub owner/repository")
    source_arguments.add_argument("--config", type=pathlib.Path, help="Tap configuration (default: taps.toml)")
    argument_parser.add_argument(
        "--date",
        type=parse_digest_date,
        default=datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1),
        help="UTC day in YYYY-MM-DD format (default: yesterday)",
    )
    argument_parser.add_argument(
        "--repository", type=pathlib.Path, help="Read local Git history at HEAD instead of cloning"
    )
    argument_parser.add_argument("--output", type=pathlib.Path, help="Write Markdown to this file (default: stdout)")
    parsed_arguments: typing.Final = argument_parser.parse_args(arguments)
    if parsed_arguments.repository is not None and parsed_arguments.tap is None:
        argument_parser.error("--repository requires --tap; use path fields for configured local taps.")
    if parsed_arguments.tap is not None:
        tap_settings: tuple[TapSettings, ...] = (
            TapSettings(
                repository_name=parsed_arguments.tap,
                repository_path=parsed_arguments.repository.resolve()
                if parsed_arguments.repository is not None
                else None,
            ),
        )
    else:
        try:
            tap_settings = load_configuration(parsed_arguments.config or pathlib.Path("taps.toml"))
        except (OSError, ValueError, tomllib.TOMLDecodeError) as failure:
            argument_parser.error(str(failure))
    try:
        tap_digests: typing.Final = collect_tap_digests(tap_settings, parsed_arguments.date)
        for tap_digest in tap_digests:
            if tap_digest.failure_message is not None:
                sys.stderr.write(f"homebrew-news: {tap_digest.tap_name}: {tap_digest.failure_message}\n")
        if parsed_arguments.tap is not None and tap_digests[0].failure_message is None:
            digest_markdown = render_digest(parsed_arguments.tap, parsed_arguments.date, tap_digests[0].package_changes)
        else:
            digest_markdown = render_grouped_digest(parsed_arguments.date, tap_digests)
        if parsed_arguments.output is None:
            sys.stdout.write(digest_markdown)
        else:
            parsed_arguments.output.parent.mkdir(parents=True, exist_ok=True)
            parsed_arguments.output.write_text(digest_markdown, encoding="utf-8")
    except (GitCommandError, OSError) as failure:
        sys.stderr.write(f"homebrew-news: {failure}\n")
        return 1
    return int(any(digest.failure_message is not None for digest in tap_digests))
