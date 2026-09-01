"""Fake py_bandcamp objects shaped like the real BandcampTrack/Album/Artist API.

Mirrors the attributes bandcamp_ma_provider actually reads (verified against
py_bandcamp 0.7.1's models.py): ``title``/``name``, ``image``, ``duration``,
``tags``, ``artist``, and ``__str__`` returning the canonical url.
"""

from __future__ import annotations


class FakeTrack:
    def __init__(self, url, title="Test Track", artist="Test Artist", image=None,
                 duration=180, tags=None):
        self.url = url
        self.title = title
        self.artist = artist
        self.image = image
        self.duration = duration
        self.tags = tags or []

    def __str__(self):
        return self.url


class FakeAlbum:
    def __init__(self, url, title="Test Album", artist="Test Artist", image=None,
                 tags=None, data=None):
        self.url = url
        self.title = title
        self.artist = artist
        self.image = image
        self.tags = tags or []
        self.data = data or {"artist": artist}

    def __str__(self):
        return self.url


class FakeArtist:
    def __init__(self, url, name="Test Artist", image=None):
        self.url = url
        self.name = name
        self.image = image

    def __str__(self):
        return self.url


class FakeBandcampTrackStrict:
    """Shaped exactly like the real py_bandcamp.models.BandcampTrack: no .tags/.keywords
    attribute (only present, if at all, inside .data), used to exercise the
    single-track-as-album path in _album_from_bc/get_album/get_album_tracks without
    masking the attribute mismatch a looser fake would hide.
    """

    def __init__(self, url, title="Single Track", artist="Single Artist", image=None,
                 duration=200, data=None):
        self.url = url
        self.title = title
        self.artist = artist
        self.image = image
        self.duration = duration
        self.data = data or {}

    def __str__(self):
        return self.url
