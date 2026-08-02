import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.dependencies import get_geocoding_service, get_ingestion_service, get_rag_service, get_routing_service
from app.main import app
from app.schemas import Activity, DayPlan, IngestedSource, SourceSnippet, TripResponse
from app.services.ingestion import IngestionError
from app.services.rag import GenerationError, UnsupportedDestinationError
from app.services.routing import RoutingError

TEST_UID = "test-uid-123"


class FakeRAGService:
    def plan_trip(self, trip, user_id):
        assert user_id == TEST_UID
        if trip.destination == "Atlantis":
            raise UnsupportedDestinationError(trip.destination)
        if trip.destination == "Paris LLM Failure":
            raise GenerationError()
        return TripResponse(
            summary=f"{trip.days} days in {trip.destination}",
            itinerary=[
                DayPlan(
                    day=1,
                    theme="Local highlights",
                    activities=[
                        Activity(
                            period="Morning",
                            title="Start local",
                            reason="Matches the request.",
                            source_titles=["Test Source"],
                        )
                    ],
                )
            ],
            sources=[
                SourceSnippet(
                    title="Test Source",
                    city=trip.destination.lower(),
                    category="general",
                    excerpt="A test source excerpt.",
                )
            ],
            generation_mode="demo",
        )

    def refine_trip(self, request, user_id):
        assert user_id == TEST_UID
        if request.trip.destination == "Atlantis":
            raise UnsupportedDestinationError(request.trip.destination)
        if request.trip.destination == "Paris LLM Failure":
            raise GenerationError()
        return TripResponse(
            summary=f"{request.current_summary} Updated: {request.instruction}",
            itinerary=request.current_itinerary,
            sources=[],
            generation_mode="demo",
        )


class FakeIngestionService:
    def __init__(self):
        self.ingested = []

    def ingest(self, user_id, destination, url):
        assert user_id == TEST_UID
        if url == "https://example.com/broken":
            raise IngestionError("Could not extract article text.")
        self.ingested.append(url)
        return {
            "url": url,
            "source_type": "blog",
            "title": "Example Article",
            "chunks_indexed": 2,
            "city": destination.lower(),
        }

    def list_sources(self, user_id, destination=None):
        assert user_id == TEST_UID
        return [
            IngestedSource(
                url="https://example.com/article",
                title="Example Article",
                source_type="blog",
                city="paris",
                ingested_at="2026-01-01T00:00:00+00:00",
                chunk_count=2,
            )
        ]

    def delete_source(self, user_id, url):
        assert user_id == TEST_UID


class FakeGeocodingService:
    def geocode(self, query):
        if query == "Nowhere":
            return None
        return (35.6762, 139.6503, f"{query} (geocoded)")


class FakeRoutingService:
    def get_route(self, coordinates):
        if len(coordinates) < 2:
            raise RoutingError("Need at least 2 points to route between.")
        return {
            "geometry": {"type": "LineString", "coordinates": [[c[1], c[0]] for c in coordinates]},
            "distance_m": 1000.0,
            "walking_duration_s": 714.3,
            "driving_duration_s": 120.0,
            "legs": [
                {
                    "distance_m": 1000.0,
                    "walking_duration_s": 714.3,
                    "driving_duration_s": 120.0,
                }
            ],
        }


@pytest.fixture
def client():
    app.dependency_overrides[get_rag_service] = lambda: FakeRAGService()
    app.dependency_overrides[get_ingestion_service] = lambda: FakeIngestionService()
    app.dependency_overrides[get_geocoding_service] = lambda: FakeGeocodingService()
    app.dependency_overrides[get_routing_service] = lambda: FakeRoutingService()
    app.dependency_overrides[get_current_user] = lambda: TEST_UID
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client():
    app.dependency_overrides[get_rag_service] = lambda: FakeRAGService()
    app.dependency_overrides[get_ingestion_service] = lambda: FakeIngestionService()
    app.dependency_overrides[get_geocoding_service] = lambda: FakeGeocodingService()
    app.dependency_overrides[get_routing_service] = lambda: FakeRoutingService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_healthcheck(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_itinerary_route_returns_trip_response(client):
    response = client.post(
        "/api/itinerary",
        json={
            "destination": "Paris",
            "days": 2,
            "budget": "mid-range",
            "interests": ["food", "art"],
            "travel_style": "couple",
            "pace": "balanced",
            "constraints": "near transit",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "2 days in Paris"
    assert body["generation_mode"] == "demo"
    assert body["itinerary"][0]["activities"][0]["source_titles"] == ["Test Source"]


def test_generate_itinerary_route_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/itinerary",
        json={
            "destination": "Paris",
            "days": 2,
            "budget": "mid-range",
            "interests": ["food"],
            "travel_style": "couple",
            "pace": "balanced",
            "constraints": "",
        },
    )

    assert response.status_code == 401


def test_generate_itinerary_route_rejects_unsupported_destination(client):
    response = client.post(
        "/api/itinerary",
        json={
            "destination": "Atlantis",
            "days": 2,
            "budget": "mid-range",
            "interests": ["food"],
            "travel_style": "couple",
            "pace": "balanced",
            "constraints": "",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "No sources found for 'Atlantis'. Add a blog or YouTube link for this destination first."
    }


def test_generate_itinerary_route_handles_generation_error(client):
    response = client.post(
        "/api/itinerary",
        json={
            "destination": "Paris LLM Failure",
            "days": 2,
            "budget": "mid-range",
            "interests": ["food"],
            "travel_style": "couple",
            "pace": "balanced",
            "constraints": "",
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The itinerary model returned an invalid response. Please try again."
    }


def test_refine_itinerary_route_returns_trip_response(client):
    payload = {
        "trip": {
            "destination": "Paris",
            "days": 1,
            "budget": "mid-range",
            "interests": ["cafes"],
            "travel_style": "solo",
            "pace": "slow",
            "constraints": "",
        },
        "current_summary": "Original plan.",
        "current_itinerary": [
            {
                "day": 1,
                "theme": "Cafes",
                "activities": [
                    {
                        "period": "Morning",
                        "title": "Coffee",
                        "reason": "Start slowly.",
                        "source_titles": ["Cafe Guide"],
                    }
                ],
            }
        ],
        "instruction": "make it quieter",
    }

    response = client.post("/api/itinerary/refine", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Original plan. Updated: make it quieter"
    assert body["itinerary"][0]["theme"] == "Cafes"


def test_refine_itinerary_route_rejects_unsupported_destination(client):
    response = client.post(
        "/api/itinerary/refine",
        json={
            "trip": {
                "destination": "Atlantis",
                "days": 1,
                "budget": "mid-range",
                "interests": ["cafes"],
                "travel_style": "solo",
                "pace": "slow",
                "constraints": "",
            },
            "current_summary": "Original plan.",
            "current_itinerary": [
                {
                    "day": 1,
                    "theme": "Cafes",
                    "activities": [
                        {
                            "period": "Morning",
                            "title": "Coffee",
                            "reason": "Start slowly.",
                            "source_titles": ["Cafe Guide"],
                        }
                    ],
                }
            ],
            "instruction": "make it quieter",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "No sources found for 'Atlantis'. Add a blog or YouTube link for this destination first."
    }


def test_refine_itinerary_route_handles_generation_error(client):
    response = client.post(
        "/api/itinerary/refine",
        json={
            "trip": {
                "destination": "Paris LLM Failure",
                "days": 1,
                "budget": "mid-range",
                "interests": ["cafes"],
                "travel_style": "solo",
                "pace": "slow",
                "constraints": "",
            },
            "current_summary": "Original plan.",
            "current_itinerary": [
                {
                    "day": 1,
                    "theme": "Cafes",
                    "activities": [
                        {
                            "period": "Morning",
                            "title": "Coffee",
                            "reason": "Start slowly.",
                            "source_titles": ["Cafe Guide"],
                        }
                    ],
                }
            ],
            "instruction": "make it quieter",
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The itinerary model returned an invalid response. Please try again."
    }


def test_ingest_source_route(client):
    response = client.post(
        "/api/sources",
        json={"destination": "Paris", "url": "https://example.com/article"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "https://example.com/article"
    assert body["chunks_indexed"] == 2
    assert body["city"] == "paris"


def test_ingest_source_route_returns_422_on_ingestion_error(client):
    response = client.post(
        "/api/sources",
        json={"destination": "Paris", "url": "https://example.com/broken"},
    )

    assert response.status_code == 422


def test_list_sources_route(client):
    response = client.get("/api/sources", params={"destination": "Paris"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["url"] == "https://example.com/article"


def test_delete_source_route(client):
    response = client.request("DELETE", "/api/sources", json={"url": "https://example.com/article"})

    assert response.status_code == 200
    assert response.json() == {"deleted": True}


def test_sources_route_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.get("/api/sources")

    assert response.status_code == 401


def test_geocode_route_returns_coordinates(client):
    response = client.get("/api/geocode", params={"query": "Tsukiji Outer Market, Tokyo"})

    assert response.status_code == 200
    body = response.json()
    assert body["lat"] == 35.6762
    assert body["lng"] == 139.6503
    assert body["label"] == "Tsukiji Outer Market, Tokyo (geocoded)"


def test_geocode_route_returns_404_when_not_found(client):
    response = client.get("/api/geocode", params={"query": "Nowhere"})

    assert response.status_code == 404


def test_geocode_route_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.get("/api/geocode", params={"query": "Tokyo"})

    assert response.status_code == 401


def test_directions_route_returns_route(client):
    response = client.post(
        "/api/directions",
        json={"coordinates": [[35.6762, 139.6503], [35.66, 139.70]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["distance_m"] == 1000.0
    assert body["driving_duration_s"] == 120.0
    assert len(body["legs"]) == 1
    assert body["legs"][0]["driving_duration_s"] == 120.0


def test_directions_route_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/directions",
        json={"coordinates": [[35.6762, 139.6503], [35.66, 139.70]]},
    )

    assert response.status_code == 401


def test_directions_route_requires_at_least_two_coordinates(client):
    response = client.post("/api/directions", json={"coordinates": [[35.6762, 139.6503]]})

    assert response.status_code == 422
