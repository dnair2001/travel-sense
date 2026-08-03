import pytest

from app.services.geocoding import GeocodingService, clean_geocode_query, strip_generic_descriptor


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Explore Tsukiji Outer Market, Tokyo", "Tsukiji Outer Market, Tokyo"),
        ("Visit the Louvre, Paris", "Louvre, Paris"),
        ("Visit Shibuya, Tokyo", "Shibuya, Tokyo"),
        ("Discover Alfama, Lisbon", "Alfama, Lisbon"),
        ("Wander through Le Marais, Paris", "Le Marais, Paris"),
        ("Tsukiji Outer Market, Tokyo", "Tsukiji Outer Market, Tokyo"),
        ("Flexible evening option", "Flexible evening option"),
        ("Imperial Palace's East Gardens, Tokyo", "Imperial Palace East Gardens, Tokyo"),
        ("Visit the Queen's Gardens, London", "Queen Gardens, London"),
        ("Shinjuku District, Tokyo", "Shinjuku, Tokyo"),
        ("Asakusa Neighborhood, Tokyo", "Asakusa, Tokyo"),
        ("French Quarter, New Orleans", "French Quarter, New Orleans"),
    ],
)
def test_clean_geocode_query_strips_leading_verb_phrase(query, expected):
    assert clean_geocode_query(query) == expected


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Shinjuku District, Tokyo", "Shinjuku, Tokyo"),
        ("Asakusa Neighborhood, Tokyo", "Asakusa, Tokyo"),
        ("Shibuya Area, Tokyo", "Shibuya, Tokyo"),
        ("Roppongi Ward, Tokyo", "Roppongi, Tokyo"),
        ("French Quarter, New Orleans", None),  # "Quarter" deliberately not stripped
        ("Shinjuku, Tokyo", None),  # nothing to strip
    ],
)
def test_strip_generic_descriptor(query, expected):
    assert strip_generic_descriptor(query) == expected


def test_geocode_strips_generic_descriptor_before_searching(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    calls = []

    def fake_get(*args, **kwargs):
        query = kwargs["params"]["q"]
        calls.append(query)
        # The raw "District" phrase is never searched -- if it were, this
        # fake would return nothing and the test would fail, since real
        # Nominatim behaves the same way for this exact query.
        if query == "Shinjuku, Tokyo":
            return FakeHttpResponse([{"lat": "35.69", "lon": "139.70", "display_name": "Shinjuku, Tokyo, Japan"}])
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Shinjuku District, Tokyo")

    assert result == (35.69, 139.70, "Shinjuku, Tokyo, Japan", False)
    assert "Shinjuku District, Tokyo" not in calls


def test_geocode_falls_back_to_dropping_leading_word(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    calls = []

    def fake_get(*args, **kwargs):
        query = kwargs["params"]["q"]
        calls.append(query)
        # "Odaiba Rainbow Bridge, Tokyo" gets zero results on real Nominatim;
        # only the bare landmark name resolves.
        if query == "Rainbow Bridge, Tokyo":
            return FakeHttpResponse([{"lat": "35.64", "lon": "139.76", "display_name": "Rainbow Bridge, Tokyo, Japan"}])
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Odaiba Rainbow Bridge, Tokyo")

    assert result == (35.64, 139.76, "Rainbow Bridge, Tokyo, Japan", False)
    assert "Odaiba Rainbow Bridge, Tokyo" in calls
    assert "Rainbow Bridge, Tokyo" in calls


def test_geocode_does_not_drop_leading_word_from_single_word_venue(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs["params"]["q"])
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    # "Yayoi-ken" is a single-word (hyphenated) venue name with no fixed
    # single address -- there's nothing to drop, and it should just fail
    # rather than searching a blank/nonsensical query.
    result = service.geocode("Yayoi-ken, Tokyo")

    assert result is None
    # Only the destination viewbox lookup and the one real search happen --
    # no blank/dangling query from trying to drop a word that isn't there.
    assert calls == ["Tokyo", "Yayoi-ken, Tokyo"]


def test_geocode_falls_back_to_trailing_location_phrase(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    calls = []

    def fake_get(*args, **kwargs):
        query = kwargs["params"]["q"]
        calls.append(query)
        if query == "Lisbon":
            return FakeHttpResponse([{"lat": "38.7", "lon": "-9.1", "boundingbox": ["38.6", "38.8", "-9.3", "-9.0"]}])
        if query == "Dinner in Bairro Alto, Lisbon":
            return FakeHttpResponse([])
        return FakeHttpResponse([{"lat": "38.71", "lon": "-9.14", "display_name": "Bairro Alto, Lisbon"}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Dinner in Bairro Alto, Lisbon")

    assert result == (38.71, -9.14, "Bairro Alto, Lisbon", False)
    # Resolves the destination's bounding box first (from the text after the
    # last comma), then searches the full query, then the fallback phrase.
    assert calls == ["Lisbon", "Dinner in Bairro Alto, Lisbon", "Bairro Alto, Lisbon"]


def test_geocode_falls_back_to_any_venue_in_city_for_chain_names(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    def fake_get(*args, **kwargs):
        params = kwargs["params"]
        if params["q"] == "Tokyo":
            return FakeHttpResponse(
                [{"lat": "35.68", "lon": "139.65", "boundingbox": ["35.5", "35.9", "139.5", "139.9"]}]
            )
        if params.get("limit") == 10:
            # Broad, unrestricted-by-name search: noise (a park, a pharmacy)
            # ranked ahead of the one real restaurant branch, mirroring what
            # real Nominatim returns for "Yayoi-ken" bounded to Tokyo.
            return FakeHttpResponse(
                [
                    {"lat": "35.9", "lon": "139.5", "display_name": "Yayoi Park", "class": "leisure", "type": "park"},
                    {
                        "lat": "35.5",
                        "lon": "139.6",
                        "display_name": "Yayoi Pharmacy",
                        "class": "amenity",
                        "type": "pharmacy",
                    },
                    {
                        "lat": "35.65",
                        "lon": "139.7",
                        "display_name": "Yayoi-ken, Yokohama, Japan",
                        "class": "amenity",
                        "type": "restaurant",
                    },
                ]
            )
        # The exact-name search (limit=1) never finds this chain by name alone.
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Yayoi-ken, Tokyo")

    assert result == (35.65, 139.7, "Yayoi-ken, Yokohama, Japan", False)


def test_geocode_any_venue_fallback_picks_nearest_candidate(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    def fake_get(*args, **kwargs):
        params = kwargs["params"]
        if params["q"] == "Tokyo":
            # Destination anchor point: (35.68, 139.65).
            return FakeHttpResponse(
                [{"lat": "35.68", "lon": "139.65", "boundingbox": ["35.5", "35.9", "139.5", "139.9"]}]
            )
        if params.get("limit") == 10:
            # Real Nominatim doesn't return these in distance order -- the
            # nearer branch is ranked second here, and should still win.
            return FakeHttpResponse(
                [
                    {
                        "lat": "35.9",
                        "lon": "139.9",
                        "display_name": "Far branch",
                        "class": "amenity",
                        "type": "restaurant",
                    },
                    {
                        "lat": "35.681",
                        "lon": "139.651",
                        "display_name": "Near branch",
                        "class": "amenity",
                        "type": "restaurant",
                    },
                ]
            )
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Yayoi-ken, Tokyo")

    assert result == (35.681, 139.651, "Near branch", False)


def test_geocode_falls_back_to_destination_center_when_nothing_matches_by_name(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    def fake_get(*args, **kwargs):
        params = kwargs["params"]
        if params["q"] == "Tokyo":
            return FakeHttpResponse(
                [{"lat": "35.68", "lon": "139.65", "boundingbox": ["35.5", "35.9", "139.5", "139.9"]}]
            )
        # Nothing matches by name at any radius -- not the exact query, not
        # any of its rewrites, not the tight or day-trip any-venue searches.
        return FakeHttpResponse([])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Completely Made Up Place, Tokyo")

    # Rather than dropping the pin entirely, falls back to the destination's
    # own center point, clearly flagged as approximate.
    assert result == (35.68, 139.65, "Approximate location near Tokyo", True)


def test_geocode_restricts_search_to_destination_viewbox(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    captured_params = []

    def fake_get(*args, **kwargs):
        params = kwargs["params"]
        captured_params.append(params)
        if params["q"] == "Tokyo":
            return FakeHttpResponse(
                [{"lat": "35.68", "lon": "139.65", "boundingbox": ["35.5", "35.9", "139.5", "139.9"]}]
            )
        return FakeHttpResponse([{"lat": "35.66", "lon": "139.7", "display_name": "Some Place, Tokyo"}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    service.geocode("Korean BBQ Restaurant, Tokyo")

    viewbox_lookup, activity_lookup = captured_params
    assert viewbox_lookup["q"] == "Tokyo"
    assert "viewbox" not in viewbox_lookup
    assert activity_lookup["q"] == "Korean BBQ Restaurant, Tokyo"
    assert activity_lookup["bounded"] == 1
    # Padded by 1 degree on every side of the resolved Tokyo bounding box.
    assert activity_lookup["viewbox"] == "138.5,36.9,140.9,34.5"


def test_geocode_skips_viewbox_when_query_has_no_destination_hint(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    captured_params = []

    def fake_get(*args, **kwargs):
        captured_params.append(kwargs["params"])
        return FakeHttpResponse([{"lat": "35.68", "lon": "139.65", "display_name": "Tokyo"}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    service.geocode("Tokyo")

    assert len(captured_params) == 1
    assert "viewbox" not in captured_params[0]


class FakeHttpResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_geocode_returns_lat_lng_label(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr(
        "app.services.geocoding.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse(
            [{"lat": "35.6762", "lon": "139.6503", "display_name": "Tokyo, Japan"}]
        ),
    )

    result = service.geocode("Tokyo")

    assert result == (35.6762, 139.6503, "Tokyo, Japan", False)


def test_geocode_returns_none_when_no_results(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.httpx.get", lambda *args, **kwargs: FakeHttpResponse([]))

    assert service.geocode("Nonexistent Place Xyz") is None


def test_geocode_returns_none_on_blank_query():
    service = GeocodingService()

    assert service.geocode("   ") is None


def test_geocode_caches_repeated_queries(monkeypatch):
    service = GeocodingService()
    call_count = 0

    def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return FakeHttpResponse([{"lat": "48.8566", "lon": "2.3522", "display_name": "Paris, France"}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    first = service.geocode("Paris")
    second = service.geocode("Paris")

    assert first == second
    assert call_count == 1


def test_geocode_handles_request_failure(monkeypatch):
    import httpx

    service = GeocodingService()

    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    assert service.geocode("Somewhere") is None
