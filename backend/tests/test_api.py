import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_rag_service
from app.main import app
from app.schemas import Activity, DayPlan, SourceSnippet, TripResponse
from app.services.rag import FeedbackPersistenceError, GenerationError, UnsupportedDestinationError


class FakeRAGService:
    def plan_trip(self, trip):
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

    def refine_trip(self, request):
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

    def record_activity_feedback(self, feedback):
        if feedback.title == "__FAIL__":
            raise FeedbackPersistenceError("disk write failed")
        return {"message": f"Saved {feedback.rating} feedback for {feedback.title}."}


@pytest.fixture
def client():
    app.dependency_overrides[get_rag_service] = lambda: FakeRAGService()
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
        "detail": "Unsupported destination 'Atlantis'. Available destinations: Paris, Tokyo, NYC."
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
        "detail": "Unsupported destination 'Atlantis'. Available destinations: Paris, Tokyo, NYC."
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


def test_record_activity_feedback_route(client):
    response = client.post(
        "/api/feedback",
        json={
            "destination": "Tokyo",
            "day": 2,
            "period": "Afternoon",
            "title": "Daikanyama T-Site",
            "rating": "love",
            "note": "Great bookstore and cafe fit.",
            "source_titles": ["Saved Places Tokyo"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "saved": True,
        "message": "Saved love feedback for Daikanyama T-Site.",
    }


def test_record_activity_feedback_route_handles_persistence_error(client):
    response = client.post(
        "/api/feedback",
        json={
            "destination": "Tokyo",
            "day": 1,
            "period": "Morning",
            "title": "__FAIL__",
            "rating": "love",
            "note": "",
            "source_titles": [],
        },
    )

    assert response.status_code == 500
    assert "Failed to save feedback" in response.json()["detail"]
