"""Check release versions and regenerate into a temporary tree to detect drift."""

import ast
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import typing

import yaml

ROOT: typing.Final = pathlib.Path(__file__).resolve().parents[1]
RELEASE_EXTRAS: typing.Final = {
    ("toml", ".ai-rulez/config.toml", "$.plugin.version"),
    ("yaml", "src/homebrew_news/plugin.yaml", "$.version"),
}


def read_toml(path: pathlib.Path) -> dict[str, typing.Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def read_json(path: pathlib.Path) -> dict[str, typing.Any]:
    return typing.cast("dict[str, typing.Any]", json.loads(path.read_text(encoding="utf-8")))


def read_yaml_version(path: pathlib.Path) -> str:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    return str(manifest["version"])


def read_python_version(path: pathlib.Path) -> str:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return str(ast.literal_eval(node.value))
    raise ValueError(f"No __version__ assignment in {path}")


def version_errors(root: pathlib.Path) -> list[str]:
    expected = read_toml(root / "pyproject.toml")["project"]["version"]
    versions = {
        ".ai-rulez/config.toml": read_toml(root / ".ai-rulez/config.toml")["plugin"]["version"],
        "src/homebrew_news/plugin.yaml": read_yaml_version(root / "src/homebrew_news/plugin.yaml"),
        ".config/release-please-manifest.json": read_json(root / ".config/release-please-manifest.json")["."],
        ".hermes/package/pyproject.toml": read_toml(root / ".hermes/package/pyproject.toml")["project"]["version"],
    }
    for plugin_dir in (
        ".hermes/plugins/homebrew-news",
        ".hermes/package/src/homebrew_news_hermes_plugin",
    ):
        versions[f"{plugin_dir}/plugin.yaml"] = read_yaml_version(root / plugin_dir / "plugin.yaml")
        versions[f"{plugin_dir}/__init__.py"] = read_python_version(root / plugin_dir / "__init__.py")
    for package in read_toml(root / "uv.lock")["package"]:
        if package["name"] == "homebrew-news" and package.get("source") == {"editable": "."}:
            versions["uv.lock"] = package["version"]
            break
    else:
        versions["uv.lock"] = "missing editable package"
    headings = re.findall(r"^##\s+\[?(\d+\.\d+\.\d+[^\s\]]*)", (root / "CHANGELOG.md").read_text(), re.MULTILINE)
    if headings:
        versions["CHANGELOG.md"] = headings[0]
    return [
        f"{path}: version {actual!r} differs from pyproject.toml {expected!r}"
        for path, actual in versions.items()
        if actual != expected
    ]


def release_config_errors(root: pathlib.Path) -> list[str]:
    config = read_json(root / ".config/release-please-config.json")
    package = config["packages"]["."]
    actual_extras = {(extra["type"], extra["path"], extra["jsonpath"]) for extra in package["extra-files"]}
    errors = []
    if config.get("release-type") != "python":
        errors.append("release-please must use the python strategy to update pyproject.toml")
    if package.get("changelog-path") != "CHANGELOG.md":
        errors.append("release-please must maintain CHANGELOG.md")
    if actual_extras != RELEASE_EXTRAS:
        errors.append("release-please extra-files must cover the native manifest and AI Rulez source version")
    return errors


def dependency_errors(root: pathlib.Path) -> list[str]:
    expected = read_toml(root / "pyproject.toml")["project"]["dependencies"]
    manifest = yaml.safe_load((root / "src/homebrew_news/plugin.yaml").read_text(encoding="utf-8"))
    if manifest.get("python_dependencies") != expected:
        return ["src/homebrew_news/plugin.yaml: Python dependencies differ from pyproject.toml"]
    return []


def generated_paths(root: pathlib.Path) -> set[str]:
    return {
        *read_json(root / ".ai-rulez/.generated-manifest.json")["files"],
        *read_json(root / ".ai-rulez-generated.json")["outputs"],
        ".ai-rulez/.generated-manifest.json",
        ".ai-rulez-generated.json",
    }


def generated_errors(root: pathlib.Path) -> list[str]:
    binary = shutil.which("ai-rulez")
    if binary is None:
        raise RuntimeError("Run this check through uv so the locked AI Rulez tool is available.")
    with tempfile.TemporaryDirectory(prefix="homebrew-news-generated-") as directory:
        temporary_root = pathlib.Path(directory)
        for source in (".ai-rulez", "src"):
            shutil.copytree(
                root / source,
                temporary_root / source,
                ignore=shutil.ignore_patterns("__pycache__", "local", "config.local.*"),
            )
        shutil.copyfile(root / ".gitignore", temporary_root / ".gitignore")
        for flags in (("--no-local",), ("--plugin", "--no-local")):
            # The executable comes from the locked development environment; flags are constants.
            subprocess.run(  # noqa: S603
                [binary, "generate", *flags], cwd=temporary_root, check=True, capture_output=True
            )
        errors = []
        for relative_path in sorted(generated_paths(root) | generated_paths(temporary_root)):
            actual = root / relative_path
            expected = temporary_root / relative_path
            if not actual.is_file() or not expected.is_file() or actual.read_bytes() != expected.read_bytes():
                errors.append(f"{relative_path}: stale or missing generated output; run make generate")
        return errors


def main() -> None:
    errors = [*version_errors(ROOT), *dependency_errors(ROOT), *release_config_errors(ROOT), *generated_errors(ROOT)]
    if errors:
        raise SystemExit("\n".join(errors))
    sys.stdout.write(
        "Repository versions, dependencies, release configuration, and generated outputs are consistent.\n"
    )


if __name__ == "__main__":
    main()
