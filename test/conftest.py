"""Test fixtures.

``music_assistant`` (the server package, as opposed to ``music_assistant_models``)
is not published to PyPI and cannot be installed by pip/uv. Since
``bandcamp_ma_provider`` only needs two small pieces of it at import time --
``music_assistant.controllers.cache.use_cache`` and
``music_assistant.models.music_provider.MusicProvider`` -- stub modules that
match the real API are injected into ``sys.modules`` before the provider
module is imported.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest


def _install_music_assistant_stubs() -> None:
    if "music_assistant" in sys.modules:
        return

    ma = types.ModuleType("music_assistant")
    ma_controllers = types.ModuleType("music_assistant.controllers")
    ma_controllers_cache = types.ModuleType("music_assistant.controllers.cache")
    ma_models = types.ModuleType("music_assistant.models")
    ma_models_music_provider = types.ModuleType("music_assistant.models.music_provider")

    def use_cache(*_args, **_kwargs):
        """No-op stand-in for the real TTL-cache decorator."""

        def _decorator(func):
            return func

        return _decorator

    class Provider:
        """Minimal stand-in for music_assistant.models.provider.Provider."""

        def __init__(self, mass, manifest, config, supported_features=None):
            self.mass = mass
            self.manifest = manifest
            self.config = config
            self.supported_features = supported_features or set()

        @property
        def domain(self) -> str:
            return self.manifest.domain

        @property
        def instance_id(self) -> str:
            return self.config.instance_id

    class MusicProvider(Provider):
        """Minimal stand-in for music_assistant.models.music_provider.MusicProvider."""

    ma_controllers_cache.use_cache = use_cache
    ma_models_music_provider.MusicProvider = MusicProvider

    sys.modules["music_assistant"] = ma
    sys.modules["music_assistant.controllers"] = ma_controllers
    sys.modules["music_assistant.controllers.cache"] = ma_controllers_cache
    sys.modules["music_assistant.models"] = ma_models
    sys.modules["music_assistant.models.music_provider"] = ma_models_music_provider


_install_music_assistant_stubs()


@pytest.fixture
def manifest():
    return SimpleNamespace(domain="bandcamp_free", type="music")


@pytest.fixture
def provider_config():
    return SimpleNamespace(instance_id="bandcamp_free_1")


@pytest.fixture
def provider(manifest, provider_config):
    """A BandcampFreeProvider instance with handle_async_init skipped."""
    from bandcamp_ma_provider import BandcampFreeProvider, SUPPORTED_FEATURES

    prov = BandcampFreeProvider(mass=None, manifest=manifest, config=provider_config, supported_features=SUPPORTED_FEATURES)
    prov._client = SimpleNamespace()
    return prov
