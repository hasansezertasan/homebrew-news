import dataclasses
import datetime
import importlib.util
import json
import pathlib
import sys
import typing

import pytest

from homebrew_news import hermes_plugin

from . import test_digest
from .test_digest import commit_package

repository_path: typing.Final = test_digest.repository_path


@typing.final
@dataclasses.dataclass(frozen=True, slots=True)
class MemoryState:
    stored_values: dict[str, object] = dataclasses.field(default_factory=dict)
    fail_writes: bool = False

    def set(self, key: str, value: object) -> None:
        if self.fail_writes:
            raise OSError("State directory is read-only")
        self.stored_values[key] = value


@typing.final
@dataclasses.dataclass(frozen=True, slots=True)
class RecordingContext:
    state: MemoryState = dataclasses.field(default_factory=MemoryState)
    settings: dict[str, object] = dataclasses.field(default_factory=dict)
    handlers: dict[str, typing.Callable[..., str]] = dataclasses.field(default_factory=dict)
    skill_paths: dict[str, pathlib.Path] = dataclasses.field(default_factory=dict)

    def get_config(self, key: str, default: object = None) -> object:
        return self.settings.get(key, default)

    def register_tool(
        self,
        *,
        name: str,
        toolset: str,
        schema: dict[str, object],
        handler: typing.Callable[..., str],
    ) -> None:
        assert toolset == "homebrew_news"
        assert schema["name"] == name
        self.handlers[name] = handler

    def register_skill(self, name: str, path: pathlib.Path, description: str = "") -> None:
        assert path.is_file()
        assert description
        self.skill_paths[name] = path


def prepare_context(repository_path: pathlib.Path, *, fail_writes: bool = False) -> RecordingContext:
    config_path: typing.Final = repository_path / "taps.toml"
    config_path.write_text('[[taps]]\nrepository = "example/tap"\npath = "."', encoding="utf-8")
    return RecordingContext(settings={"config_path": str(config_path)}, state=MemoryState(fail_writes=fail_writes))


def test_registered_handler_collects_real_repository(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Add tool")
    plugin_context: typing.Final = prepare_context(repository_path)
    hermes_plugin.register(plugin_context)

    tool_result: typing.Final = json.loads(
        plugin_context.handlers["homebrew_news_digest"](
            {"date": "2026-10-04"},
            task_id="task-context",
            session_id="session-context",
        )
    )

    assert tool_result["status"] == "ok"
    assert tool_result["taps"][0]["counts"] == {"added": 1, "updated": 0, "removed": 0}
    assert tool_result["taps"][0]["changes"][0]["commit_url"].startswith("https://github.com/example/tap/commit/")
    assert "**tool**" in tool_result["markdown"]
    assert plugin_context.skill_paths["write-news"].is_file()
    assert plugin_context.state.stored_values["last_collection"]


def test_limits_detail_without_losing_full_counts(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/first.rb", "v1", "First")
    commit_package(repository_path, "Formula/second.rb", "v1", "Second")
    plugin_context: typing.Final = prepare_context(repository_path)
    digest_tool: typing.Final = hermes_plugin.DigestTool(context=plugin_context, plugin_root=repository_path)

    tool_result: typing.Final = json.loads(digest_tool.run_digest({"date": "2026-10-04", "limit": 1}))

    assert tool_result["status"] == "ok"
    assert tool_result["taps"][0]["total_changes"] == 2
    assert tool_result["taps"][0]["counts"]["added"] == 2
    assert len(tool_result["taps"][0]["changes"]) == 1
    assert tool_result["taps"][0]["truncated"] is True
    assert "Showing 1 of 2" in tool_result["markdown"]


def test_partial_results_only_record_successful_taps(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Add tool")
    plugin_context: typing.Final = prepare_context(repository_path)
    config_path: typing.Final = repository_path / "taps.toml"
    with config_path.open("a", encoding="utf-8") as config_stream:
        config_stream.write('\n[[taps]]\nrepository = "example/missing"\npath = "missing"')
    digest_tool: typing.Final = hermes_plugin.DigestTool(context=plugin_context, plugin_root=repository_path)

    tool_result: typing.Final = json.loads(digest_tool.run_digest({"date": "2026-10-04"}))

    assert tool_result["status"] == "partial"
    assert tool_result["failed_taps"] == 1
    assert tool_result["taps"][1]["status"] == "error"
    assert "**Partial digest:**" in tool_result["markdown"]
    collection_metadata: typing.Final = plugin_context.state.stored_values["last_collection"]
    assert isinstance(collection_metadata, dict)
    assert collection_metadata["date"] == "2026-10-04"
    assert collection_metadata["successful_taps"] == ["example/tap"]
    assert collection_metadata["failed_taps"] == ["example/missing"]
    assert datetime.datetime.fromisoformat(collection_metadata["collected_at"]).tzinfo is not None


def test_all_failures_do_not_update_state(tmp_path: pathlib.Path) -> None:
    plugin_context: typing.Final = prepare_context(tmp_path)
    digest_tool: typing.Final = hermes_plugin.DigestTool(context=plugin_context, plugin_root=tmp_path)

    tool_result: typing.Final = json.loads(digest_tool.run_digest({"date": "2026-10-04"}))

    assert tool_result["status"] == "error"
    assert "All configured taps failed" in tool_result["error"]
    assert not plugin_context.state.stored_values


def test_state_failure_preserves_collected_news(repository_path: pathlib.Path) -> None:
    commit_package(repository_path, "Formula/tool.rb", "v1", "Add tool")
    plugin_context: typing.Final = prepare_context(repository_path, fail_writes=True)
    digest_tool: typing.Final = hermes_plugin.DigestTool(context=plugin_context, plugin_root=repository_path)

    tool_result: typing.Final = json.loads(digest_tool.run_digest({"date": "2026-10-04"}))

    assert tool_result["status"] == "ok"
    assert "could not be saved" in tool_result["warning"]
    assert tool_result["taps"][0]["total_changes"] == 1


@pytest.mark.parametrize(
    "tool_arguments",
    [
        {"date": "2026-02-30"},
        {"date": "20261004"},
        {"date": 123},
        {"date": "9999-12-31"},
        {"tap": "../bad"},
        {"tap": 123},
        {"limit": 0},
        {"limit": 201},
        {"limit": True},
        {"limit": "50"},
        {"unknown": "typo"},
    ],
)
def test_invalid_arguments_return_json_errors(tmp_path: pathlib.Path, tool_arguments: dict[str, object]) -> None:
    digest_tool: typing.Final = hermes_plugin.DigestTool(context=RecordingContext(), plugin_root=tmp_path)

    tool_result: typing.Final = json.loads(digest_tool.run_digest(tool_arguments))

    assert tool_result["status"] == "error"
    assert tool_result["error"]


def test_defaults_and_tap_override(tmp_path: pathlib.Path) -> None:
    plugin_context: typing.Final = RecordingContext(settings={"config_path": "missing.toml"})

    overridden_taps: typing.Final = hermes_plugin.resolve_plugin_taps(plugin_context, tmp_path, "example/tap")
    default_taps: typing.Final = hermes_plugin.resolve_plugin_taps(RecordingContext(), tmp_path, None)
    digest_date, requested_limit = hermes_plugin.parse_tool_arguments({})

    assert overridden_taps[0].repository_name == "example/tap"
    assert default_taps[0].repository_name == "Homebrew/homebrew-core"
    assert digest_date == datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    assert requested_limit == 50


@pytest.mark.parametrize(
    "entry_point",
    [
        "__init__.py",
        ".hermes/plugins/homebrew-news/__init__.py",
        ".hermes/package/src/homebrew_news_hermes_plugin/__init__.py",
    ],
)
def test_directory_entry_points_collect_real_repository(repository_path: pathlib.Path, entry_point: str) -> None:
    commit_package(repository_path, "Formula/native.rb", "v1", "Native import")
    plugin_context: typing.Final = prepare_context(repository_path)
    project_root: typing.Final = pathlib.Path(__file__).parents[1]
    entry_point_path: typing.Final = project_root / entry_point
    module_name: typing.Final = "_isolated_homebrew_plugin"
    plugin_spec: typing.Final = importlib.util.spec_from_file_location(
        module_name,
        entry_point_path,
        submodule_search_locations=[str(entry_point_path.parent)],
    )
    assert plugin_spec is not None
    assert plugin_spec.loader is not None
    plugin_module: typing.Final = importlib.util.module_from_spec(plugin_spec)
    sys.modules[module_name] = plugin_module
    try:
        plugin_spec.loader.exec_module(plugin_module)
        plugin_module.register(plugin_context)
        tool_result = json.loads(plugin_context.handlers["homebrew_news_digest"]({"date": "2026-10-04"}))
        assert tool_result["status"] == "ok"
        assert tool_result["taps"][0]["changes"][0]["package_name"] == "native"
        handler_module = plugin_context.handlers["homebrew_news_digest"].__module__
        if entry_point == "__init__.py":
            assert handler_module.startswith(module_name + ".")
        else:
            assert handler_module == "homebrew_news.hermes_plugin"
    finally:
        for loaded_name in tuple(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(module_name + "."):
                del sys.modules[loaded_name]
