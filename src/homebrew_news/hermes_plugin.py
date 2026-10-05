import dataclasses
import datetime
import json
import logging
import pathlib
import typing

from .config import ConfigurationError, TapSettings, load_configuration, validate_tap_name
from .digest import TapDigest, render_grouped_digest

LOGGER: typing.Final = logging.getLogger(__name__)
MAX_CHANGES: typing.Final = 200
TOOL_SCHEMA: typing.Final[dict[str, object]] = {
    "name": "homebrew_news_digest",
    "description": (
        "Collect daily additions, updates, and removals from Homebrew tap Git history. "
        "Returns structured changes, full counts, commit links, and Markdown. "
        "Use for Homebrew package news; default day is yesterday UTC and default tap is Homebrew/homebrew-core. "
        "Updated means a file changed, not necessarily a version upgrade. "
        "For a readable summary, load skill homebrew-news:write-news. Large results are explicitly truncated."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "UTC calendar day, YYYY-MM-DD; defaults to yesterday."},
            "tap": {
                "type": "string",
                "description": "Optional full GitHub owner/repository; overrides configured taps.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 50,
                "description": "Maximum returned file changes per tap; full counts are always included.",
            },
        },
        "additionalProperties": False,
    },
}


class PluginState(typing.Protocol):
    def set(self, key: str, value: object) -> None: ...


class PluginContext(typing.Protocol):
    @property
    def state(self) -> PluginState: ...

    def get_config(self, key: str, default: object = None) -> object: ...

    def register_tool(
        self,
        *,
        name: str,
        toolset: str,
        schema: dict[str, object],
        handler: typing.Callable[..., str],
    ) -> object: ...

    def register_skill(self, name: str, path: pathlib.Path, description: str = "") -> object: ...


def resolve_plugin_taps(
    context: PluginContext, plugin_root: pathlib.Path, requested_tap: object
) -> tuple[TapSettings, ...]:
    if requested_tap is not None:
        if not isinstance(requested_tap, str):
            raise ValueError("tap must be a GitHub owner/repository string.")
        return (TapSettings(repository_name=validate_tap_name(requested_tap)),)
    config_path: typing.Final = context.get_config("config_path", default="")
    if not isinstance(config_path, str):
        raise ConfigurationError("config_path must be a string.")
    if config_path:
        return load_configuration(plugin_root / config_path)
    configured_taps: typing.Final = context.get_config("taps", default=["Homebrew/homebrew-core"])
    if not isinstance(configured_taps, list) or not configured_taps:
        raise ConfigurationError("Plugin taps setting must be a nonempty list of GitHub repository names.")
    tap_settings: typing.Final[list[TapSettings]] = []
    seen_repositories: typing.Final[set[str]] = set()
    for repository_name in configured_taps:
        if not isinstance(repository_name, str):
            raise ConfigurationError("Each configured tap must be a string.")
        validate_tap_name(repository_name)
        if repository_name.lower() in seen_repositories:
            raise ConfigurationError(f"Duplicate tap: {repository_name}")
        seen_repositories.add(repository_name.lower())
        tap_settings.append(TapSettings(repository_name=repository_name))
    return tuple(tap_settings)


def parse_tool_arguments(arguments: dict[str, object]) -> tuple[datetime.date, int]:
    if set(arguments) - {"date", "tap", "limit"}:
        raise ValueError("Supported arguments are date, tap, and limit.")
    requested_date: typing.Final = arguments.get("date")
    if requested_date is None:
        digest_date = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    else:
        if not isinstance(requested_date, str):
            raise ValueError("date must use YYYY-MM-DD format.")
        digest_date = datetime.date.fromisoformat(requested_date)
        if requested_date != digest_date.isoformat() or digest_date == datetime.date.max:
            raise ValueError("date must use YYYY-MM-DD format and leave room for the next day.")
    requested_limit: typing.Final = arguments.get("limit", 50)
    if (
        isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or not 1 <= requested_limit <= MAX_CHANGES
    ):
        raise ValueError("limit must be an integer between 1 and 200.")
    return digest_date, requested_limit


def build_tap_result(tap_digest: TapDigest, requested_limit: int) -> dict[str, object]:
    return {
        "tap": tap_digest.tap_name,
        "status": "error" if tap_digest.failure_message is not None else "ok",
        "error": tap_digest.failure_message,
        "total_changes": len(tap_digest.package_changes),
        "counts": {
            change_kind.lower(): sum(change.change_kind == change_kind for change in tap_digest.package_changes)
            for change_kind in ("Added", "Updated", "Removed")
        },
        "truncated": len(tap_digest.package_changes) > requested_limit,
        "changes": [
            {
                **dataclasses.asdict(package_change),
                "commit_url": f"https://github.com/{tap_digest.tap_name}/commit/{package_change.commit_hash}",
            }
            for package_change in tap_digest.package_changes[:requested_limit]
        ],
    }


@typing.final
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class DigestTool:
    context: PluginContext
    plugin_root: pathlib.Path

    def run_digest(self, arguments: dict[str, object], **_context_keywords: object) -> str:
        try:
            return json.dumps(self.collect_digest(arguments), ensure_ascii=False)
        except (ValueError, OSError) as failure:
            return json.dumps({"status": "error", "error": str(failure)})
        except ModuleNotFoundError as failure:
            return json.dumps(
                {
                    "status": "error",
                    "error": f"Missing Python module {failure.name!r}; "
                    "prepare the plugin's declared dependencies through Hermes enablement.",
                }
            )
        except Exception:
            LOGGER.exception("Homebrew news tool failed")
            return json.dumps({"status": "error", "error": "Unexpected collection error; check Hermes logs."})

    def collect_digest(self, arguments: dict[str, object]) -> dict[str, object]:
        digest_date, requested_limit = parse_tool_arguments(arguments)
        tap_settings: typing.Final = resolve_plugin_taps(self.context, self.plugin_root, arguments.get("tap"))
        # Keep registration independent of collector dependencies; Hermes admits them on enablement.
        from .service import collect_tap_digests  # noqa: PLC0415

        tap_digests: typing.Final = collect_tap_digests(tap_settings, digest_date)
        failed_count: typing.Final = sum(digest.failure_message is not None for digest in tap_digests)
        result_payload: typing.Final[dict[str, object]] = {
            "status": "error" if failed_count == len(tap_digests) else "partial" if failed_count else "ok",
            "date": digest_date.isoformat(),
            "timezone": "UTC",
            "failed_taps": failed_count,
            "limit_per_tap": requested_limit,
            "taps": [build_tap_result(digest, requested_limit) for digest in tap_digests],
            "markdown": render_grouped_digest(digest_date, tap_digests, max_changes=requested_limit),
        }
        if failed_count == len(tap_digests):
            result_payload["error"] = "All configured taps failed; see individual tap errors."
        successful_taps: typing.Final = [digest for digest in tap_digests if digest.failure_message is None]
        if successful_taps:
            try:
                self.context.state.set(
                    "last_collection",
                    {
                        "date": digest_date.isoformat(),
                        "collected_at": datetime.datetime.now(datetime.UTC).isoformat(),
                        "successful_taps": [digest.tap_name for digest in successful_taps],
                        "failed_taps": [
                            digest.tap_name for digest in tap_digests if digest.failure_message is not None
                        ],
                    },
                )
            except (OSError, ValueError) as failure:
                result_payload["warning"] = f"Digest collected, but collection metadata could not be saved: {failure}"
        return result_payload


def register(context: PluginContext, *, plugin_root: pathlib.Path | None = None) -> None:
    package_path: typing.Final = pathlib.Path(__file__).parent
    digest_tool: typing.Final = DigestTool(context=context, plugin_root=plugin_root or package_path)
    context.register_tool(
        name="homebrew_news_digest", toolset="homebrew_news", schema=TOOL_SCHEMA, handler=digest_tool.run_digest
    )
    context.register_skill(
        "write-news",
        package_path / "skills" / "write-news" / "SKILL.md",
        description="Write a sourced Homebrew news summary from collected tap changes.",
    )
