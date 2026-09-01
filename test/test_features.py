from __future__ import annotations

from music_assistant_models.enums import ProviderFeature

from bandcamp_ma_provider import SUPPORTED_FEATURES, BandcampFreeProvider


def test_browse_is_implemented():
    """browse() must be a real override, not the base class's NotImplementedError."""
    assert BandcampFreeProvider.browse is not None
    assert "browse" in BandcampFreeProvider.__dict__


def test_browse_feature_is_declared():
    """
    Regression test for the BROWSE feature-flag bug: browse() is implemented
    but was missing from SUPPORTED_FEATURES, so Music Assistant never exposed
    the browse UI for this provider even though it worked.
    """
    assert ProviderFeature.BROWSE in SUPPORTED_FEATURES


def test_declared_features_match_implemented_methods():
    """SUPPORTED_FEATURES should declare exactly what BandcampFreeProvider implements."""
    implemented = {
        ProviderFeature.SEARCH: "search",
        ProviderFeature.BROWSE: "browse",
        ProviderFeature.ARTIST_ALBUMS: "get_artist_albums",
        ProviderFeature.ARTIST_TOPTRACKS: "get_artist_toptracks",
        ProviderFeature.RECOMMENDATIONS: "get_recommendations",
    }
    for feature, method_name in implemented.items():
        assert method_name in BandcampFreeProvider.__dict__, (
            f"{feature} declared but {method_name} is not overridden"
        )
    for feature in SUPPORTED_FEATURES:
        assert feature in implemented, f"{feature} declared but not accounted for"
