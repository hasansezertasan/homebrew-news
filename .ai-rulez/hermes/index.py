"""Bridge AI Rulez bundles to the installed homebrew-news implementation."""

import pathlib

from homebrew_news.hermes_plugin import PluginContext
from homebrew_news.hermes_plugin import register as register_plugin


def register(context: PluginContext) -> None:
    register_plugin(context, plugin_root=pathlib.Path(__file__).parent)
