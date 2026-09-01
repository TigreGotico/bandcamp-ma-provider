from __future__ import annotations

from unittest.mock import patch

import pytest
from music_assistant_models.errors import MediaNotFoundError

from .fakes import FakeAlbum, FakeArtist, FakeTrack


@pytest.mark.asyncio
async def test_get_track_happy_path(provider):
    track_id = "https://artist.bandcamp.com/track/song"
    fake = FakeTrack(url=track_id, title="Song")
    with (
        patch("py_bandcamp.utils.get_stream_data", return_value={"title": "Song"}),
        patch("py_bandcamp.models.BandcampTrack", return_value=fake),
    ):
        track = await provider.get_track(track_id)

    assert track.item_id == track_id
    assert track.name == "Song"


@pytest.mark.asyncio
async def test_get_track_upstream_error_becomes_media_not_found(provider):
    track_id = "https://artist.bandcamp.com/track/missing"
    with patch("py_bandcamp.utils.get_stream_data", side_effect=ValueError("HTTP 404 fetching")):
        with pytest.raises(MediaNotFoundError):
            await provider.get_track(track_id)


@pytest.mark.asyncio
async def test_get_album_happy_path(provider):
    album_id = "https://artist.bandcamp.com/album/lp"
    fake = FakeAlbum(url=album_id, title="LP")
    with patch("py_bandcamp.models.BandcampAlbum.from_url", return_value=fake):
        album = await provider.get_album(album_id)

    assert album.item_id == album_id
    assert album.name == "LP"


@pytest.mark.asyncio
async def test_get_album_upstream_error_becomes_media_not_found(provider):
    album_id = "https://artist.bandcamp.com/album/missing"
    with patch("py_bandcamp.models.BandcampAlbum.from_url", side_effect=ValueError("404")):
        with pytest.raises(MediaNotFoundError):
            await provider.get_album(album_id)


@pytest.mark.asyncio
async def test_get_artist_happy_path(provider):
    artist_id = "https://artist.bandcamp.com"
    fake = FakeArtist(url=artist_id, name="Artist")
    with patch("py_bandcamp.models.BandcampArtist.from_url", return_value=fake):
        artist = await provider.get_artist(artist_id)

    assert artist.item_id == artist_id
    assert artist.name == "Artist"


@pytest.mark.asyncio
async def test_get_artist_upstream_error_becomes_media_not_found(provider):
    artist_id = "https://artist.bandcamp.com"
    with patch("py_bandcamp.models.BandcampArtist.from_url", side_effect=ValueError("404")):
        with pytest.raises(MediaNotFoundError):
            await provider.get_artist(artist_id)
