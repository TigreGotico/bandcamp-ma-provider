"""
Regression coverage for the BandcampSingle removal.

py_bandcamp.models has no BandcampSingle class (verified against every released
py_bandcamp version up to 0.7.1). The original code unconditionally imported it
for "/track/" (single) urls in _album_from_bc, get_album, and get_album_tracks,
which made every single-as-album lookup raise ImportError -- including from
search()'s album results, since _album_from_bc imported it regardless of
single vs. full album. The fix falls back to the underlying BandcampTrack for
the single-url case. These tests fail if that fallback is reverted.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from music_assistant_models.enums import AlbumType, MediaType

from .fakes import FakeBandcampTrackStrict


SINGLE_URL = "https://artist.bandcamp.com/track/a-single"


@pytest.mark.asyncio
async def test_get_album_maps_single_track_url(provider):
    fake = FakeBandcampTrackStrict(
        url=SINGLE_URL,
        title="A Single",
        artist="Single Artist",
        image="https://f.bcbits.com/img/single.jpg",
        data={"keywords": ["synthwave"]},
    )
    with patch("py_bandcamp.models.BandcampTrack.from_url", return_value=fake):
        album = await provider.get_album(SINGLE_URL)

    assert album.item_id == SINGLE_URL
    assert album.name == "A Single"
    assert album.album_type == AlbumType.SINGLE
    assert album.artists[0].name == "Single Artist"
    assert album.metadata.images[0].path == fake.image
    # cosmetic fallback: genre tags read from .data when not exposed as an attribute
    assert album.metadata.genres == {"synthwave"}


@pytest.mark.asyncio
async def test_get_album_tracks_single_url_returns_one_track(provider):
    fake = FakeBandcampTrackStrict(url=SINGLE_URL, title="A Single", artist="Single Artist")
    with patch("py_bandcamp.models.BandcampTrack.from_url", return_value=fake):
        tracks = await provider.get_album_tracks(SINGLE_URL)

    assert len(tracks) == 1
    assert tracks[0].item_id == SINGLE_URL
    assert tracks[0].name == "A Single"
    assert tracks[0].artists[0].name == "Single Artist"


@pytest.mark.asyncio
async def test_search_albums_maps_single_track_result(provider):
    """search()'s album branch runs every result through _album_from_bc, singles
    included (e.g. a single surfaced by search_albums)."""
    fake = FakeBandcampTrackStrict(url=SINGLE_URL, title="A Single", artist="Single Artist")
    with patch.object(provider._client, "search_albums", return_value=iter([fake]), create=True):
        result = await provider.search("a single", [MediaType.ALBUM], limit=10)

    assert len(result.albums) == 1
    album = result.albums[0]
    assert album.item_id == SINGLE_URL
    assert album.album_type == AlbumType.SINGLE
    assert album.name == "A Single"
