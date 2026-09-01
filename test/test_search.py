from __future__ import annotations

from unittest.mock import patch

import pytest
from music_assistant_models.enums import MediaType

from .fakes import FakeAlbum, FakeArtist, FakeTrack


@pytest.mark.asyncio
async def test_search_tracks_maps_fields(provider):
    fake = FakeTrack(
        url="https://artist.bandcamp.com/track/some-song",
        title="Some Song",
        artist="Some Artist",
        image="https://f.bcbits.com/img/a.jpg",
        duration=210,
        tags=["lofi", "chill"],
    )
    with patch.object(provider._client, "search_tracks", return_value=iter([fake]), create=True):
        result = await provider.search("some song", [MediaType.TRACK], limit=10)

    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert track.item_id == fake.url
    assert track.provider == provider.domain
    assert track.name == "Some Song"
    assert track.duration == 210
    assert track.metadata.genres == {"lofi", "chill"}
    assert len(track.artists) == 1
    assert track.artists[0].name == "Some Artist"
    assert track.metadata.images[0].path == fake.image
    mapping = next(iter(track.provider_mappings))
    assert mapping.item_id == fake.url
    assert mapping.provider_domain == provider.domain
    assert mapping.provider_instance == provider.instance_id


@pytest.mark.asyncio
async def test_search_albums_maps_fields(provider):
    fake = FakeAlbum(
        url="https://artist.bandcamp.com/album/some-album",
        title="Some Album",
        artist="Some Artist",
    )
    with patch.object(provider._client, "search_albums", return_value=iter([fake]), create=True):
        result = await provider.search("some album", [MediaType.ALBUM], limit=10)

    assert len(result.albums) == 1
    album = result.albums[0]
    assert album.item_id == fake.url
    assert album.name == "Some Album"
    assert album.artists[0].name == "Some Artist"


@pytest.mark.asyncio
async def test_search_artists_maps_fields(provider):
    fake = FakeArtist(url="https://artist.bandcamp.com", name="Some Artist")
    with patch.object(provider._client, "search_artists", return_value=iter([fake]), create=True):
        result = await provider.search("some artist", [MediaType.ARTIST], limit=10)

    assert len(result.artists) == 1
    artist = result.artists[0]
    assert artist.item_id == fake.url
    assert artist.name == "Some Artist"


@pytest.mark.asyncio
async def test_search_respects_limit(provider):
    fakes = [FakeTrack(url=f"https://a.bandcamp.com/track/{i}") for i in range(5)]
    with patch.object(provider._client, "search_tracks", return_value=iter(fakes), create=True):
        result = await provider.search("x", [MediaType.TRACK], limit=2)

    assert len(result.tracks) == 2


@pytest.mark.asyncio
async def test_search_only_requested_media_types(provider):
    with (
        patch.object(provider._client, "search_tracks", return_value=iter([]), create=True) as tracks_mock,
        patch.object(provider._client, "search_albums", return_value=iter([]), create=True),
    ):
        result = await provider.search("x", [MediaType.ALBUM])
    tracks_mock.assert_not_called()
    assert result.tracks == []
