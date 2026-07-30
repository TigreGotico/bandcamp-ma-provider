# bandcamp-ma-provider

[Music Assistant](https://music-assistant.io) provider for [Bandcamp](https://bandcamp.com). It searches and streams free and name-your-price tracks without a Bandcamp account, using [`py_bandcamp`](https://github.com/TigreGotico/py_bandcamp).

| Provider domain | Content |
|---|---|
| `bandcamp_free` | Tracks, albums, artists; browse by tag; album recommendations |

Stream URLs are resolved at play-time directly from Bandcamp's public MP3 stream endpoint. No credentials, no API key, no OAuth.

---

## Table of contents

- [Quick start](#quick-start)
- [What you get](#what-you-get)
- [How it works](#how-it-works)
- [Provider reference](#provider-reference)
- [Architecture deep-dive](#architecture-deep-dive)
- [Development guide](#development-guide)
- [Troubleshooting](#troubleshooting)

---

## Quick start

### 1. Install

```bash
pip install bandcamp-ma-provider
```

Dependencies pulled in automatically:

| Package | Role |
|---|---|
| `music-assistant-plugin-manager` | Registers the provider with MA at startup |
| `py_bandcamp` | Bandcamp search, artist/album pages, stream URL resolution |

### 2. Launch Music Assistant through the plugin manager

```bash
mass-pm
```

### 3. Enable the provider

In Music Assistant: **Settings → Providers → Bandcamp (no login) → +**

There are no configuration fields. Click + to enable the provider.

---

## What you get

**Search**: tracks, albums, artists by keyword.

**Artist pages**: navigate to an artist from a search result or a track. The artist page shows their discography (albums and singles).

**Album pages**: full track listing. Singles (Bandcamp `/track/` URLs) are modelled as single-track albums of type `SINGLE`.

**Browse by tag**: the Browse section exposes Bandcamp's tag system. The top level shows up to 30 popular tags; opening a tag lists tracks tagged with it.

**Recommendations**: from an album page, MA can request similar albums via Bandcamp's recommendation engine.

**What is not available**: tracks that require purchase (even $1 minimum). Only tracks with a free or name-your-price stream are playable. Bandcamp's stream endpoint returns a 128 kbps MP3.

---

## How it works

```
User searches "Electric Wizard"
         │
         └─ BandcampFreeProvider.search()
                └─ BandCamp.search_tracks("Electric Wizard")     ← py_bandcamp
                   BandCamp.search_albums("Electric Wizard")
                   BandCamp.search_artists("Electric Wizard")

User presses Play on a track
         │
         └─ get_stream_details(item_id="https://electricwizard.bandcamp.com/track/...")
                └─ BandCamp.get_stream_url(item_id)              ← py_bandcamp
                         └─ fetches Bandcamp's hidden MP3 stream URL
                              └─ StreamDetails(HTTP, MP3, 128 kbps)
                                   └─ MA fetches and plays
```

Stream resolution results are cached for 10 minutes (`@use_cache(600)`) because Bandcamp's stream URLs are short-lived but stable within a session.

---

## Provider reference

**Source**: `bandcamp_ma_provider/__init__.py`  
**Domain**: `bandcamp_free`  
**Audio format**: MP3, 128 kbps (Bandcamp's free-tier stream)

### Supported features

| Feature | Description |
|---|---|
| `SEARCH` | Tracks, albums, artists |
| `ARTIST_ALBUMS` | Full discography including singles |
| `ARTIST_TOPTRACKS` | Tracks from the artist's featured album |
| `RECOMMENDATIONS` | Similar albums via Bandcamp's recommendation engine |
| `BROWSE` | Tag-based browsing (top tags → tracks per tag) |

### Media type mapping

| MA type | Bandcamp concept | item\_id format |
|---|---|---|
| `Track` | Individual track | `https://<artist>.bandcamp.com/track/<slug>` |
| `Album` | Album | `https://<artist>.bandcamp.com/album/<slug>` |
| `Album` (type=SINGLE) | Single (track page with no parent album) | `https://<artist>.bandcamp.com/track/<slug>` |
| `Artist` | Artist / label | `https://<artist>.bandcamp.com` |

Item IDs are always full Bandcamp URLs. This lets `get_album()` and `get_artist()` pass the URL straight to `py_bandcamp`.

### Methods

| Method | What it does |
|---|---|
| `search(query, media_types, limit)` | Searches Bandcamp for tracks, albums, and/or artists |
| `get_track(prov_track_id)` | Fetches track metadata from the Bandcamp page |
| `get_album(prov_album_id)` | Fetches album or single metadata |
| `get_album_tracks(prov_album_id)` | Fetches track listing (handles both albums and singles) |
| `get_artist(prov_artist_id)` | Fetches artist page metadata |
| `get_artist_toptracks(prov_artist_id)` | Returns tracks from the artist's featured album |
| `get_artist_albums(prov_artist_id)` | Returns all albums and singles for an artist |
| `get_recommendations(media_type, item_id)` | Returns similar albums (album items only) |
| `browse(path)` | Returns tag folders at root, tracks per tag one level deep |
| `get_stream_details(item_id, media_type)` | Resolves track URL to MP3 stream (cached 10 min) |

### Artist item\_id derivation

Bandcamp track and album URLs encode the artist: `https://<artist>.bandcamp.com/track/<slug>`. The helpers `_artist_url_from_track()` and `_artist_item_id()` extract the base URL (`https://<artist>.bandcamp.com`) and use it as the artist's `item_id`. This means clicking an artist from a track result correctly navigates to their full artist page without an extra lookup.

If the artist URL cannot be derived (for example, the URL does not contain `/track/` or `/album/`), the artist name string is used as item_id instead. Lookups for those artists then fail without crashing the provider.

### Singles vs. albums

Bandcamp sometimes publishes tracks directly under `/track/` without a parent album. `_album_from_bc()` detects this via `isinstance(alb, BandcampSingle) or "/track/" in url` and sets `album_type=AlbumType.SINGLE`. `get_album_tracks()` handles both cases: it calls `BandcampSingle.from_url()` for `/track/` URLs and `BandcampAlbum.from_url()` for `/album/` URLs.

### Browse path format

Paths use the form `<domain>://<segments>`. The root path (`bandcamp_free://` with no segments) returns up to 30 tag folders. A tag path (`bandcamp_free://doom-metal`) searches Bandcamp for that tag and returns up to 20 tracks. Tags come from `BandCamp.tags()` which fetches Bandcamp's public tag directory.

---

## Architecture deep-dive

### Discovery

This package registers itself via a setuptools entrypoint:

```toml
[project.entry-points."music_assistant.provider"]
bandcamp_free = "bandcamp_ma_provider"
```

When `mass-pm` starts, `music-assistant-plugin-manager` reads this entrypoint and injects the `bandcamp_free` domain into MA's provider registry before MA's own startup code runs. See [plugin-managers](https://github.com/TigreGotico/plugin-managers) for the full mechanism.

### Stream resolution and caching

`get_stream_details()` is decorated with `@use_cache(600)`:

```python
@use_cache(600)
async def get_stream_details(self, item_id: str, media_type: MediaType) -> StreamDetails:
    stream_url = await asyncio.to_thread(self._client.get_stream_url, item_id)
    ...
```

`use_cache` is MA's built-in cache decorator, backed by its internal cache controller. A TTL of 600 seconds (10 minutes) covers normal listening sessions. Bandcamp stream URLs expire faster than that, but stay stable within a session.

The guard `if not stream_url or stream_url == item_id` catches the case where `py_bandcamp` returns the original page URL unchanged (what happens when no free stream is available), which would otherwise cause an infinite redirect loop in MA's player.

### Blocking calls and `asyncio.to_thread`

Every `py_bandcamp` call is synchronous (HTTP + HTML parsing). All are wrapped in `asyncio.to_thread()` so the MA event loop is never blocked:

```python
tracks = await asyncio.to_thread(
    lambda: list(self._client.search_tracks(search_query))[:limit]
)
```

### Lazy imports

`py_bandcamp` model classes (`BandcampAlbum`, `BandcampSingle`, `BandcampArtist`, etc.) are imported inside the methods that use them, not at module level:

```python
async def get_album(self, prov_album_id: str) -> Album:
    from py_bandcamp.models import BandcampAlbum, BandcampSingle  # noqa: PLC0415
    ...
```

This keeps module import time fast and keeps each dependency visible at the call site where it matters.

---

## Development guide

### Set up

```bash
git clone https://github.com/TigreGotico/bandcamp-ma-provider
cd bandcamp-ma-provider
pip install -e .
```

Also install `py_bandcamp` from source if you need to debug it:

```bash
git clone https://github.com/TigreGotico/py_bandcamp
pip install -e ../py_bandcamp
```

### Explore the `py_bandcamp` API

```python
from py_bandcamp import BandCamp

# Search
for t in BandCamp.search_tracks("electric wizard"):
    print(t.title, str(t))          # str(t) is the track URL / item_id

for a in BandCamp.search_albums("electric wizard"):
    print(a.title, a.image, str(a))

for a in BandCamp.search_artists("electric wizard"):
    print(a.name, a.image, str(a))

# Artist page
from py_bandcamp.models import BandcampArtist
art = BandcampArtist.from_url("https://electricwizard.bandcamp.com")
print(art.name, art.image)
albums, singles = BandcampArtist.get_albums(str(art), include_singles=True)

# Album page
from py_bandcamp.models import BandcampAlbum
alb = BandcampAlbum.from_url("https://electricwizard.bandcamp.com/album/dopethrone")
for t in alb.tracks:
    print(t.title, t.duration)
recs = BandcampAlbum.get_recommendations(str(alb))

# Stream URL
url = BandCamp.get_stream_url("https://electricwizard.bandcamp.com/track/funeralopolis")
print(url)   # direct MP3 URL, or the page URL if not freely streamable
```

### Adding a new feature flag

To add, for example, `ProviderFeature.LIBRARY_TRACKS`:

1. Add `ProviderFeature.LIBRARY_TRACKS` to `SUPPORTED_FEATURES`.
2. Implement `async def get_library_tracks(self)`. This requires a user library concept, which Bandcamp does not expose publicly. This step is a placeholder example.

In practice, useful additions are more likely `ProviderFeature.BROWSE` extensions (e.g. genre sub-folders, new release feeds) using Bandcamp's tag and discover APIs.

---

## Troubleshooting

### "No free stream available"

`get_stream_details` raises `MediaNotFoundError` when `BandCamp.get_stream_url()` returns nothing or the original page URL. This means the track requires purchase. Only free/name-your-price tracks are playable.

### Search returns very few results

Bandcamp's public search returns the first result page only. For niche queries this may be 3–5 results. This is a Bandcamp API limitation, not a bug.

### Artist page shows no albums

`BandcampArtist.get_albums()` scrapes the artist's discography page. If Bandcamp changes its page structure this may return empty. Update `py_bandcamp` first:

```bash
pip install -U py_bandcamp
```

### Tracks are missing artist or image metadata

Some Bandcamp search result pages omit these fields. The `_clean_artist_name()` helper handles the case where the "artist" field is a URL (Bandcamp sometimes embeds the profile URL instead of a name) by extracting the subdomain as a display name.

### Provider not appearing in MA

```bash
python -c "
from music_assistant_plugin_manager import find_providers
print(find_providers())
"
# expected: {"bandcamp_free": "bandcamp_ma_provider", ...}
```

If missing: verify `pip install bandcamp-ma-provider` succeeded and that you are running `mass-pm`, not `music-assistant` directly.
