"""Bandcamp provider for Music Assistant via py_bandcamp (no login required)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING

from music_assistant_models.enums import (
    AlbumType,
    ContentType,
    ImageType,
    MediaType,
    ProviderFeature,
    StreamType,
)
from music_assistant_models.errors import MediaNotFoundError, ProviderUnavailableError
from music_assistant_models.media_items import (
    Album,
    Artist,
    AudioFormat,
    BrowseFolder,
    ItemMapping,
    MediaItemImage,
    MediaItemType,
    ProviderMapping,
    SearchResults,
    Track,
    UniqueList,
)
from music_assistant_models.streamdetails import StreamDetails

from music_assistant.controllers.cache import use_cache
from music_assistant.models.music_provider import MusicProvider

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ConfigEntry, ConfigValueType, ProviderConfig
    from music_assistant_models.provider import ProviderManifest
    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType

SUPPORTED_FEATURES = {
    ProviderFeature.SEARCH,
    ProviderFeature.BROWSE,
    ProviderFeature.ARTIST_ALBUMS,
    ProviderFeature.ARTIST_TOPTRACKS,
    ProviderFeature.RECOMMENDATIONS,
}


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    return BandcampFreeProvider(mass, manifest, config, SUPPORTED_FEATURES)


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    return ()


def _image(url: str | None, instance_id: str) -> MediaItemImage | None:
    if not url:
        return None
    return MediaItemImage(type=ImageType.THUMB, path=url, provider=instance_id, remotely_accessible=True)


def _clean_artist_name(name: str) -> str:
    if not name:
        return "Unknown"
    if name.startswith("http"):
        return name.rstrip("/").split("//")[-1].split(".")[0]
    return name


def _artist_url_from_track(track_url: str) -> str | None:
    """Derive the artist base URL from a Bandcamp track/album URL."""
    for seg in ("/track/", "/album/"):
        if seg in track_url:
            return track_url.split(seg)[0]
    return None


def _artist_item_id(track_url: str, artist_name: str) -> str:
    """Return a canonical artist item_id: the artist base URL if derivable, else the name."""
    url = _artist_url_from_track(track_url)
    return url if url else _clean_artist_name(artist_name)


def _artist_mapping(name: str, domain: str, item_id: str | None = None) -> ItemMapping:
    resolved_id = item_id or _clean_artist_name(name)
    return ItemMapping(media_type=MediaType.ARTIST, item_id=resolved_id, provider=domain, name=_clean_artist_name(name))


def _track_from_bc(t, domain: str, instance_id: str, artist_override: str | None = None) -> Track:
    url = str(t)
    track = Track(
        item_id=url,
        provider=domain,
        name=t.title or url.split("/")[-1],
        provider_mappings={
            ProviderMapping(
                item_id=url,
                provider_domain=domain,
                provider_instance=instance_id,
                audio_format=AudioFormat(content_type=ContentType.MP3, bit_rate=128),
            )
        },
        duration=int(getattr(t, "duration", None) or 0),
    )
    raw_artist = artist_override or getattr(t, "artist", None) or "Unknown"
    artist_name = raw_artist if isinstance(raw_artist, str) else getattr(raw_artist, "name", "Unknown")
    artist_id = _artist_item_id(url, artist_name)
    track.artists = UniqueList([_artist_mapping(artist_name, domain, item_id=artist_id)])
    img = _image(getattr(t, "image", None), instance_id)
    if img:
        track.metadata.images = UniqueList([img])
    tags = getattr(t, "tags", None) or getattr(t, "keywords", None) or []
    if tags:
        track.metadata.genres = set(tags)
    return track


def _album_from_bc(alb, domain: str, instance_id: str) -> Album:
    url = str(alb)
    is_single = "/track/" in url
    album = Album(
        item_id=url,
        provider=domain,
        name=alb.title or url.split("/")[-1],
        album_type=AlbumType.SINGLE if is_single else AlbumType.ALBUM,
        provider_mappings={
            ProviderMapping(item_id=url, provider_domain=domain, provider_instance=instance_id)
        },
    )
    img = _image(alb.image, instance_id)
    if img:
        album.metadata.images = UniqueList([img])
    tags = (
        getattr(alb, "tags", None)
        or getattr(alb, "keywords", None)
        or (alb.data.get("keywords") if hasattr(alb, "data") else None)
        or []
    )
    if tags:
        album.metadata.genres = set(tags)
    artist_raw = getattr(alb, "artist", None) or (alb.data.get("artist") if hasattr(alb, "data") else None) or ""
    if artist_raw:
        name = artist_raw if isinstance(artist_raw, str) else getattr(artist_raw, "name", "")
        if name:
            artist_id = _artist_url_from_track(url) or name
            album.artists = UniqueList([_artist_mapping(name, domain, item_id=artist_id)])
    return album


def _artist_from_bc(art, domain: str, instance_id: str) -> Artist:
    url = str(art)
    artist = Artist(
        item_id=url,
        provider=domain,
        name=art.name or url.split("/")[-1],
        provider_mappings={
            ProviderMapping(item_id=url, provider_domain=domain, provider_instance=instance_id)
        },
    )
    img = _image(art.image, instance_id)
    if img:
        artist.metadata.images = UniqueList([img])
    return artist


class BandcampFreeProvider(MusicProvider):
    """Music Assistant provider for Bandcamp free/pay-what-you-want content."""

    @property
    def is_streaming_provider(self) -> bool:
        return True

    async def handle_async_init(self) -> None:
        try:
            from py_bandcamp import BandCamp  # noqa: PLC0415
            self._client = BandCamp
        except ImportError as err:
            raise ProviderUnavailableError("py_bandcamp not installed") from err

    async def search(
        self, search_query: str, media_types: list[MediaType], limit: int = 10
    ) -> SearchResults:
        result = SearchResults()

        if MediaType.TRACK in media_types:
            tracks = await asyncio.to_thread(
                lambda: list(self._client.search_tracks(search_query))[:limit]
            )
            result.tracks = [_track_from_bc(t, self.domain, self.instance_id) for t in tracks]

        if MediaType.ALBUM in media_types:
            albums = await asyncio.to_thread(
                lambda: list(self._client.search_albums(search_query))[:limit]
            )
            result.albums = [_album_from_bc(a, self.domain, self.instance_id) for a in albums]

        if MediaType.ARTIST in media_types:
            artists = await asyncio.to_thread(
                lambda: list(self._client.search_artists(search_query))[:limit]
            )
            result.artists = [_artist_from_bc(a, self.domain, self.instance_id) for a in artists]

        return result

    async def browse(self, path: str) -> Sequence[MediaItemType | BrowseFolder]:
        parts = [p for p in path.split("://")[1].split("/") if p] if "://" in path else []
        if not parts:
            tags = await asyncio.to_thread(self._client.tags)
            return [
                BrowseFolder(
                    item_id=tag,
                    provider=self.domain,
                    path=f"{path}/{tag}",
                    name=tag.replace("-", " ").title(),
                )
                for tag in tags[:30]
            ]
        tag = parts[0]
        tracks = await asyncio.to_thread(lambda: list(self._client.search_tracks(tag))[:20])
        return [_track_from_bc(t, self.domain, self.instance_id) for t in tracks]

    async def get_track(self, prov_track_id: str) -> Track:
        from py_bandcamp.utils import get_stream_data  # noqa: PLC0415
        from py_bandcamp.models import BandcampTrack  # noqa: PLC0415
        try:
            data = await asyncio.to_thread(get_stream_data, prov_track_id)
            t = BandcampTrack({"url": prov_track_id, **data}, parse=False)
        except Exception as err:
            raise MediaNotFoundError(f"Track not found: {prov_track_id}") from err
        return _track_from_bc(t, self.domain, self.instance_id)

    async def get_album(self, prov_album_id: str) -> Album:
        from py_bandcamp.models import BandcampAlbum, BandcampTrack  # noqa: PLC0415
        try:
            if "/track/" in prov_album_id:
                # a Bandcamp "single" is served from a /track/ url; py_bandcamp has no
                # dedicated single/EP model, so treat it as its underlying track page.
                alb = await asyncio.to_thread(BandcampTrack.from_url, prov_album_id)
            else:
                alb = await asyncio.to_thread(BandcampAlbum.from_url, prov_album_id)
        except Exception as err:
            raise MediaNotFoundError(f"Album not found: {prov_album_id}") from err
        return _album_from_bc(alb, self.domain, self.instance_id)

    async def get_album_tracks(self, prov_album_id: str) -> list[Track]:
        from py_bandcamp.models import BandcampAlbum, BandcampTrack  # noqa: PLC0415

        def _do():
            if "/track/" in prov_album_id:
                # a Bandcamp "single" is served from a /track/ url and is its own
                # sole track; py_bandcamp has no dedicated single/EP model.
                t = BandcampTrack.from_url(prov_album_id)
                artist_raw = getattr(t, "artist", None) or ""
                artist_name = artist_raw if isinstance(artist_raw, str) else getattr(artist_raw, "name", "")
                return [t], artist_name
            alb = BandcampAlbum.from_url(prov_album_id)
            artist_raw = alb.data.get("artist") or ""
            artist_name = artist_raw if isinstance(artist_raw, str) else getattr(artist_raw, "name", "")
            return alb.tracks, artist_name

        tracks, artist_name = await asyncio.to_thread(_do)
        return [_track_from_bc(t, self.domain, self.instance_id, artist_override=artist_name or None) for t in tracks]

    async def get_artist(self, prov_artist_id: str) -> Artist:
        from py_bandcamp.models import BandcampArtist  # noqa: PLC0415
        try:
            art = await asyncio.to_thread(BandcampArtist.from_url, prov_artist_id)
        except Exception as err:
            raise MediaNotFoundError(f"Artist not found: {prov_artist_id}") from err
        return _artist_from_bc(art, self.domain, self.instance_id)

    async def get_artist_toptracks(self, prov_artist_id: str) -> list[Track]:
        from py_bandcamp.models import BandcampArtist  # noqa: PLC0415

        def _do():
            art = BandcampArtist.from_url(prov_artist_id)
            fa = art.featured_album
            return fa.tracks if fa else []

        tracks = await asyncio.to_thread(_do)
        return [_track_from_bc(t, self.domain, self.instance_id) for t in tracks]

    async def get_artist_albums(self, prov_artist_id: str) -> list[Album]:
        from py_bandcamp.models import BandcampArtist  # noqa: PLC0415

        def _do():
            albums, singles = BandcampArtist.get_albums(prov_artist_id, include_singles=True)
            return albums + singles

        items = await asyncio.to_thread(_do)
        return [_album_from_bc(a, self.domain, self.instance_id) for a in items]

    async def get_recommendations(self, media_type: MediaType, item_id: str) -> list:
        if media_type != MediaType.ALBUM:
            return []
        from py_bandcamp.models import BandcampAlbum  # noqa: PLC0415
        recs = await asyncio.to_thread(BandcampAlbum.get_recommendations, item_id)
        return [_album_from_bc(a, self.domain, self.instance_id) for a in recs]

    @use_cache(600)
    async def get_stream_details(self, item_id: str, media_type: MediaType) -> StreamDetails:
        stream_url = await asyncio.to_thread(self._client.get_stream_url, item_id)
        if not stream_url or stream_url == item_id:
            raise MediaNotFoundError(f"No free stream available for: {item_id}")
        return StreamDetails(
            provider=self.domain,
            item_id=item_id,
            audio_format=AudioFormat(content_type=ContentType.MP3, bit_rate=128),
            media_type=MediaType.TRACK,
            stream_type=StreamType.HTTP,
            path=stream_url,
            can_seek=True,
            allow_seek=True,
        )
