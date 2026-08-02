import pytest

from app.services.geocoding import GeocodingService, clean_geocode_query


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
    ],
)
def test_clean_geocode_query_strips_leading_verb_phrase(query, expected):
    assert clean_geocode_query(query) == expected


def test_geocode_falls_back_to_trailing_location_phrase(monkeypatch):
    service = GeocodingService()
    monkeypatch.setattr("app.services.geocoding.GeocodingService._throttle", lambda self: None)

    calls = []

    def fake_get(*args, **kwargs):
        query = kwargs["params"]["q"]
        calls.append(query)
        if query == "Dinner in Bairro Alto, Lisbon":
            return FakeHttpResponse([])
        return FakeHttpResponse([{"lat": "38.71", "lon": "-9.14", "display_name": "Bairro Alto, Lisbon"}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)

    result = service.geocode("Dinner in Bairro Alto, Lisbon")

    assert result == (38.71, -9.14, "Bairro Alto, Lisbon")
    assert calls == ["Dinner in Bairro Alto, Lisbon", "Bairro Alto, Lisbon"]


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

    assert result == (35.6762, 139.6503, "Tokyo, Japan")


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
