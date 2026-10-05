"""Native Hermes directory-plugin entry point."""

import pathlib

from .src.homebrew_news.hermes_plugin import PluginContext
from .src.homebrew_news.hermes_plugin import register as register_plugin


def register(context: PluginContext) -> None:
    register_plugin(context, plugin_root=pathlib.Path(__file__).parent)
