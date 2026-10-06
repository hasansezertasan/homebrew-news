import pathlib
import tempfile
import typing

from .collector import GitCommandError, HistoryLimitError, clone_repository, collect_changes
from .digest import TapDigest

if typing.TYPE_CHECKING:
    import datetime

    from .config import TapSettings


def collect_tap_digests(tap_settings: tuple[TapSettings, ...], digest_date: datetime.date) -> tuple[TapDigest, ...]:
    tap_digests: typing.Final[list[TapDigest]] = []
    for configured_tap in tap_settings:
        try:
            if configured_tap.repository_path is not None:
                package_changes = collect_changes(configured_tap.repository_path, digest_date)
            else:
                with tempfile.TemporaryDirectory(prefix="homebrew-news-") as temporary_directory:
                    repository_path = pathlib.Path(temporary_directory) / "tap.git"
                    clone_repository(configured_tap.repository_name, repository_path, digest_date)
                    package_changes = collect_changes(repository_path, digest_date, allow_shallow=True)
        except (GitCommandError, HistoryLimitError, OSError) as failure:
            tap_digests.append(TapDigest(tap_name=configured_tap.repository_name, failure_message=str(failure)))
        else:
            tap_digests.append(TapDigest(tap_name=configured_tap.repository_name, package_changes=package_changes))
    return tuple(tap_digests)
