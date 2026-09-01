from __future__ import annotations

import importlib.metadata


def test_entry_point_resolves_to_provider_package():
    eps = importlib.metadata.entry_points(group="music_assistant.provider")
    matches = [ep for ep in eps if ep.name == "bandcamp_free"]
    assert matches, "no 'bandcamp_free' entry point registered under music_assistant.provider"
    ep = matches[0]
    assert ep.value == "bandcamp_ma_provider"
    module = ep.load()
    assert hasattr(module, "setup")
    assert hasattr(module, "SUPPORTED_FEATURES")
