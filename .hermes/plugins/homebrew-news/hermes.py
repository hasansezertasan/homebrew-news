# AI-RULEZ :: GENERATED FILE — DO NOT EDIT
# Content-Hash: blake3:918ff38d3c9a9237fadb8715308dab3b25ea0dd048d0b69f62f9644eeea5f732
# Source-Hash: blake3:791bd0bb07e6cef4a1e7f14c0ff0272b8c12659b83d1fb8868f6aa421b5af453
# Schema-Version: v1

"""Bridge AI Rulez bundles to the installed homebrew-news implementation."""

import pathlib

from homebrew_news.hermes_plugin import PluginContext
from homebrew_news.hermes_plugin import register as register_plugin


def register(context: PluginContext) -> None:
    register_plugin(context, plugin_root=pathlib.Path(__file__).parent)
