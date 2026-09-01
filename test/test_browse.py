from __future__ import annotations

from unittest.mock import patch

import pytest
from music_assistant_models.media_items import BrowseFolder, Track

from .fakes import FakeTrack


@pytest.mark.asyncio
async def test_browse_root_lists_tags_as_folders(provider):
    tags = ["lo-fi", "ambient"]
    with patch.object(provider._client, "tags", return_value=tags, create=True):
        items = await provider.browse("bandcamp_free://")

    assert len(items) == 2
    assert all(isinstance(i, BrowseFolder) for i in items)
    assert items[0].item_id == "lo-fi"
    assert items[0].name == "Lo Fi"
    assert items[0].path == "bandcamp_free:///lo-fi"


@pytest.mark.asyncio
async def test_browse_tag_folder_lists_tracks(provider):
    fake = FakeTrack(url="https://artist.bandcamp.com/track/song")
    with patch.object(provider._client, "search_tracks", return_value=iter([fake]), create=True):
        items = await provider.browse("bandcamp_free://lo-fi")

    assert len(items) == 1
    assert isinstance(items[0], Track)
    assert items[0].item_id == fake.url


@pytest.mark.asyncio
async def test_browse_root_caps_at_30_tags(provider):
    tags = [f"tag-{i}" for i in range(50)]
    with patch.object(provider._client, "tags", return_value=tags, create=True):
        items = await provider.browse("bandcamp_free://")

    assert len(items) == 30
