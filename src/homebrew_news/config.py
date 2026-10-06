import dataclasses
import re
import tomllib
import typing

if typing.TYPE_CHECKING:
    import pathlib


@typing.final
@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TapSettings:
    repository_name: str
    repository_path: pathlib.Path | None = None


@typing.final
class ConfigurationError(ValueError):
    """Tap configuration is invalid."""


def validate_tap_name(argument: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", argument):
        raise ValueError("Use a GitHub repository name such as owner/homebrew-tap.")
    return argument


def load_configuration(config_path: pathlib.Path) -> tuple[TapSettings, ...]:
    with config_path.open("rb") as config_stream:
        configuration: typing.Final = tomllib.load(config_stream)
    configured_taps: typing.Final = configuration.get("taps")
    if set(configuration) != {"taps"} or not isinstance(configured_taps, list) or not configured_taps:
        raise ConfigurationError("Configuration must contain a nonempty list of [[taps]] tables.")
    parsed_settings: typing.Final[list[TapSettings]] = []
    seen_repositories: typing.Final[set[str]] = set()
    for configured_tap in configured_taps:
        if not isinstance(configured_tap, dict) or set(configured_tap) - {"repository", "path"}:
            raise ConfigurationError("Each tap must be a table with repository and optional path fields.")
        repository_name = configured_tap.get("repository")
        repository_path = configured_tap.get("path")
        if not isinstance(repository_name, str):
            raise ConfigurationError("Each tap requires a repository string.")
        validate_tap_name(repository_name)
        if repository_name.lower() in seen_repositories:
            raise ConfigurationError(f"Duplicate tap: {repository_name}")
        if repository_path is not None and (not isinstance(repository_path, str) or not repository_path):
            raise ConfigurationError(f"Local path for {repository_name} must be a nonempty string.")
        seen_repositories.add(repository_name.lower())
        parsed_settings.append(
            TapSettings(
                repository_name=repository_name,
                repository_path=(config_path.parent / repository_path).resolve()
                if repository_path is not None
                else None,
            )
        )
    return tuple(parsed_settings)
