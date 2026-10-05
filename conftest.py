import pathlib

import pytest

ROOT_PATH = pathlib.Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # The repository root is the native plugin package, named after its checkout directory.
    # When that name is not an identifier, pytest cannot import its relative-import entry point
    # to look for package-level setup, and the root defines none.
    for test_item in items:
        for collection_node in test_item.listchain():
            if isinstance(collection_node, pytest.Package) and collection_node.path == ROOT_PATH:
                collection_node.setup = lambda: None  # type: ignore[method-assign]
