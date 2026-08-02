import pytest

from app.services.routing import RoutingError, RoutingService, _format_maneuver


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
                "duration": 900.2,
                "legs": [
                    {
                        "distance": 1200.5,
                        "duration": 900.2,
                        "steps": [
                            {
                                "maneuver": {"type": "depart"},
                                "name": "Harumi Dori",
                                "distance": 400.0,
                            },
                            {
                                "maneuver": {"type": "turn", "modifier": "left"},
                                "name": "Chuo Dori",
                                "distance": 700.5,
                            },
                            {
                                "maneuver": {"type": "arrive"},
                                "name": "",
                                "distance": 0.0,
                            },
                        ],
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
    # Duration is computed from distance at walking speed, not trusted from
    # OSRM (whose public demo only actually times as if driving).
    assert result["duration_s"] == pytest.approx(1200.5 / 1.4)
    assert result["geometry"]["type"] == "LineString"
    assert len(result["legs"]) == 1
    leg = result["legs"][0]
    assert leg["distance_m"] == 1200.5
    assert leg["duration_s"] == pytest.approx(1200.5 / 1.4)
    # The trailing zero-distance "arrive" step should be dropped.
    assert len(leg["steps"]) == 2
    assert leg["steps"][0]["instruction"] == "Head out on Harumi Dori"
    assert leg["steps"][1]["instruction"] == "Turn left onto Chuo Dori"


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


@pytest.mark.parametrize(
    "maneuver,name,expected",
    [
        ({"type": "depart"}, "Main St", "Head out on Main St"),
        ({"type": "arrive"}, "", "Arrive at your destination"),
        ({"type": "turn", "modifier": "right"}, "5th Ave", "Turn right onto 5th Ave"),
        ({"type": "turn", "modifier": ""}, "5th Ave", "Continue onto 5th Ave"),
        ({"type": "roundabout"}, "Ring Rd", "Enter the roundabout and take the exit onto Ring Rd"),
        ({"type": "new name"}, "Broadway", "Continue on Broadway"),
        ({"type": "continue"}, "", "Continue on the road"),
    ],
)
def test_format_maneuver(maneuver, name, expected):
    assert _format_maneuver(maneuver, name) == expected
