import pytest

from app.services.routing import RoutingError, RoutingService


class FakeHttpResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def osrm_payload():
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": {"type": "LineString", "coordinates": [[139.77, 35.665], [139.70, 35.66]]},
                "distance": 1200.5,
                "duration": 180.0,
                "legs": [
                    {
                        "distance": 1200.5,
                        "duration": 180.0,
                    }
                ],
            }
        ],
    }


def test_get_route_returns_geometry_and_legs(monkeypatch):
    service = RoutingService()
    monkeypatch.setattr(
        "app.services.routing.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse(osrm_payload()),
    )

    result = service.get_route([(35.665, 139.77), (35.66, 139.70)])

    assert result["distance_m"] == 1200.5
    # Driving duration is trusted straight from OSRM (a real car route).
    assert result["driving_duration_s"] == 180.0
    # Walking duration is derived from distance at a fixed walking pace,
    # since OSRM's public demo has no real pedestrian routing.
    assert result["walking_duration_s"] == pytest.approx(1200.5 / 1.4)
    assert result["geometry"]["type"] == "LineString"
    assert len(result["legs"]) == 1
    leg = result["legs"][0]
    assert leg["distance_m"] == 1200.5
    assert leg["driving_duration_s"] == 180.0
    assert leg["walking_duration_s"] == pytest.approx(1200.5 / 1.4)


def test_get_route_sends_lng_lat_order(monkeypatch):
    service = RoutingService()
    captured_urls = []

    def fake_get(url, **kwargs):
        captured_urls.append(url)
        return FakeHttpResponse(osrm_payload())

    monkeypatch.setattr("app.services.routing.httpx.get", fake_get)

    service.get_route([(35.665, 139.77), (35.66, 139.70)])

    assert "139.77,35.665;139.7,35.66" in captured_urls[0]


def test_get_route_requires_at_least_two_points():
    service = RoutingService()

    with pytest.raises(RoutingError):
        service.get_route([(35.665, 139.77)])


def test_get_route_raises_when_osrm_reports_no_route(monkeypatch):
    service = RoutingService()
    monkeypatch.setattr(
        "app.services.routing.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse({"code": "NoRoute", "routes": []}),
    )

    with pytest.raises(RoutingError):
        service.get_route([(35.665, 139.77), (35.66, 139.70)])


def test_get_route_handles_request_failure(monkeypatch):
    import httpx

    service = RoutingService()

    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr("app.services.routing.httpx.get", fake_get)

    with pytest.raises(RoutingError):
        service.get_route([(35.665, 139.77), (35.66, 139.70)])
