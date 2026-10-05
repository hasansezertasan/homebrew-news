import json
import pathlib
import shutil
import typing

import pytest

from scripts import check_repository


@pytest.fixture
def project_tree(tmp_path: pathlib.Path) -> pathlib.Path:
    for directory in (".ai-rulez", ".hermes", ".config", "src"):
        shutil.copytree(
            check_repository.ROOT / directory,
            tmp_path / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    for filename in ("pyproject.toml", "uv.lock", "CHANGELOG.md", ".gitignore"):
        shutil.copyfile(check_repository.ROOT / filename, tmp_path / filename)
    for relative_path in check_repository.generated_paths(check_repository.ROOT):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(check_repository.ROOT / relative_path, destination)
    return tmp_path


@pytest.mark.parametrize(
    "relative_path",
    ["src/homebrew_news/plugin.yaml", ".ai-rulez/config.toml", ".hermes/package/pyproject.toml", "uv.lock"],
)
def test_release_version_drift_is_rejected(project_tree: pathlib.Path, relative_path: str) -> None:
    assert not check_repository.version_errors(project_tree)
    target: typing.Final = project_tree / relative_path
    current_version: typing.Final = check_repository.read_toml(project_tree / "pyproject.toml")["project"]["version"]
    target.write_text(target.read_text().replace(current_version, "9.8.7"), encoding="utf-8")

    assert any(relative_path in error for error in check_repository.version_errors(project_tree))


def test_native_dependency_drift_is_rejected(project_tree: pathlib.Path) -> None:
    assert not check_repository.dependency_errors(project_tree)
    target: typing.Final = project_tree / "src/homebrew_news/plugin.yaml"
    target.write_text(target.read_text().replace("stamina>=24.3,<27", "stamina>=24.3,<26"), encoding="utf-8")

    assert check_repository.dependency_errors(project_tree)


def test_release_config_must_bump_native_manifest(project_tree: pathlib.Path) -> None:
    target: typing.Final = project_tree / ".config/release-please-config.json"
    config: typing.Final = check_repository.read_json(target)
    assert not check_repository.release_config_errors(project_tree)
    config["packages"]["."]["extra-files"] = config["packages"]["."]["extra-files"][:1]
    target.write_text(json.dumps(config), encoding="utf-8")

    assert check_repository.release_config_errors(project_tree)


@pytest.mark.parametrize("change", ["source", "output", "missing"])
def test_generated_drift_is_rejected_without_rewriting_checkout(project_tree: pathlib.Path, change: str) -> None:
    assert not check_repository.generated_errors(project_tree)
    target: typing.Final = project_tree / (".ai-rulez/context/architecture.md" if change == "source" else "AGENTS.md")
    if change == "missing":
        target.unlink()
    else:
        target.write_text(target.read_text() + "\nChanged guidance.\n", encoding="utf-8")
    before: typing.Final = target.read_bytes() if target.exists() else None

    assert check_repository.generated_errors(project_tree)
    assert (target.read_bytes() if target.exists() else None) == before
