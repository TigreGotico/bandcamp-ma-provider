from __future__ import annotations

from unittest.mock import patch

import pytest
from music_assistant_models.enums import ContentType, MediaType, StreamType
from music_assistant_models.errors import MediaNotFoundError


@pytest.mark.asyncio
async def test_get_stream_details_returns_url_with_sane_format(provider):
    item_id = "https://artist.bandcamp.com/track/song"
    stream_url = "https://t4.bcbits.com/stream/abc.mp3"
    with patch.object(provider._client, "get_stream_url", return_value=stream_url, create=True):
        details = await provider.get_stream_details(item_id, MediaType.TRACK)

    assert details.path == stream_url
    assert details.item_id == item_id
    assert details.provider == provider.domain
    assert details.stream_type == StreamType.HTTP
    assert details.audio_format.content_type == ContentType.MP3
    assert details.can_seek is True


@pytest.mark.asyncio
async def test_get_stream_details_raises_media_not_found_when_no_stream(provider):
    item_id = "https://artist.bandcamp.com/track/paid-only"
    with patch.object(provider._client, "get_stream_url", return_value=None, create=True):
        with pytest.raises(MediaNotFoundError):
            await provider.get_stream_details(item_id, MediaType.TRACK)


@pytest.mark.asyncio
async def test_get_stream_details_raises_media_not_found_when_url_echoed_back(provider):
    """py_bandcamp returns the input url unchanged when no free stream exists."""
    item_id = "https://artist.bandcamp.com/track/paid-only"
    with patch.object(provider._client, "get_stream_url", return_value=item_id, create=True):
        with pytest.raises(MediaNotFoundError):
            await provider.get_stream_details(item_id, MediaType.TRACK)
