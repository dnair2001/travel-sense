import pytest
from langchain_core.documents import Document

from app.config import Settings
from app.schemas import Activity, ActivityFeedbackRequest, DayPlan, RefinementRequest, TripRequest
from app.services.rag import GenerationError, TravelRAGService, UnsupportedDestinationError


def make_service(tmp_path):
    settings = Settings(
        openai_api_key=None,
        chroma_dir=str(tmp_path / "chroma"),
        collection_name="test-travel-sense-docs",
    )
    return TravelRAGService(settings)


def source_documents():
    return [
        Document(
            page_content="Paris food guidance.",
            metadata={
                "title": "Paris Food Logistics",
                "city": "paris",
                "category": "food_logistics",
                "scope": "destination",
            },
        )
    ]


def test_rebuild_vectorstore_indexes_source_documents(tmp_path):
    service = make_service(tmp_path)

    result = service.rebuild_vectorstore()

    assert result["documents"] == 15
    assert result["chunks"] >= 18
    assert result["cities"] == 3
    assert result["personal_documents"] == 9
    assert service.vectorstore._collection.count() == result["chunks"]


def test_retrieve_documents_filters_to_destination_city(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Paris",
        days=2,
        budget="mid-range",
        interests=["food", "art"],
        travel_style="couple",
        pace="balanced",
        constraints="near transit",
    )

    documents = service.retrieve_documents(trip)

    assert documents
    destination_documents = [doc for doc in documents if doc.metadata["scope"] == "destination"]
    personal_documents = [doc for doc in documents if doc.metadata["scope"] == "personal"]
    assert {doc.metadata["city"] for doc in destination_documents} == {"paris"}
    assert {doc.metadata["title"] for doc in destination_documents} == {
        "Paris Art Cafes",
        "Paris Food Logistics",
    }
    assert personal_documents


def test_plan_trip_demo_uses_retrieved_sources(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Tokyo",
        days=3,
        budget="budget",
        interests=["food", "transit"],
        travel_style="friends",
        pace="fast",
        constraints="avoid taxis",
    )

    response = service.plan_trip(trip)

    assert response.generation_mode == "demo"
    assert len(response.itinerary) == 3
    assert response.sources
    assert "tokyo" in {source.city for source in response.sources}
    assert "personal" in {source.city for source in response.sources}
    assert all(day.activities for day in response.itinerary)


def test_retrieve_documents_weights_destination_saved_places(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Tokyo",
        days=3,
        budget="mid-range",
        interests=["bookstores", "coffee shops", "local neighborhoods"],
        travel_style="solo explorer",
        pace="balanced",
        constraints="avoid packed schedules",
    )

    documents = service.retrieve_documents(trip)
    titles = [doc.metadata["title"] for doc in documents]

    assert "Saved Places Tokyo" in titles
    assert titles.index("Saved Places Tokyo") < len(titles) - 1


def test_plan_trip_rejects_unsupported_destination(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Atlantis",
        days=2,
        budget="mid-range",
        interests=["history"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )

    with pytest.raises(UnsupportedDestinationError) as exc_info:
        service.plan_trip(trip)

    assert exc_info.value.destination == "Atlantis"


def test_refine_trip_demo_preserves_days_and_applies_instruction(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="NYC",
        days=1,
        budget="luxury",
        interests=["neighborhoods"],
        travel_style="family",
        pace="slow",
        constraints="minimal subway transfers",
    )
    current_itinerary = [
        DayPlan(
            day=1,
            theme="Neighborhoods",
            activities=[
                Activity(
                    period="Morning",
                    title="Start uptown",
                    reason="Original reason.",
                    source_titles=["NYC Neighborhoods"],
                )
            ],
        )
    ]
    request = RefinementRequest(
        trip=trip,
        current_summary="Original NYC plan.",
        current_itinerary=current_itinerary,
        instruction="add more indoor options",
    )

    response = service.refine_trip(request)

    assert response.generation_mode == "demo"
    assert response.summary == "Original NYC plan. Updated to reflect: add more indoor options."
    assert len(response.itinerary) == 1
    assert "Refinement applied: add more indoor options." in response.itinerary[0].activities[0].reason


def test_refine_trip_rejects_unsupported_destination(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Atlantis",
        days=1,
        budget="luxury",
        interests=["neighborhoods"],
        travel_style="family",
        pace="slow",
        constraints="",
    )
    request = RefinementRequest(
        trip=trip,
        current_summary="Original plan.",
        current_itinerary=[
            DayPlan(
                day=1,
                theme="Neighborhoods",
                activities=[
                    Activity(
                        period="Morning",
                        title="Start",
                        reason="Original reason.",
                        source_titles=["Guide"],
                    )
                ],
            )
        ],
        instruction="add indoor options",
    )

    with pytest.raises(UnsupportedDestinationError) as exc_info:
        service.refine_trip(request)

    assert exc_info.value.destination == "Atlantis"


def test_parse_llm_trip_response_accepts_valid_json(tmp_path):
    service = make_service(tmp_path)
    content = """
    {
      "summary": "A focused Paris plan.",
      "itinerary": [
        {
          "day": 1,
          "theme": "Food",
          "activities": [
            {
              "period": "Morning",
              "title": "Market walk",
              "reason": "Uses source context.",
              "source_titles": ["Paris Food Logistics"]
            }
          ]
        }
      ]
    }
    """

    response = service._parse_llm_trip_response(content, source_documents())

    assert response.generation_mode == "llm"
    assert response.summary == "A focused Paris plan."
    assert response.itinerary[0].activities[0].period == "Morning"
    assert response.sources[0].title == "Paris Food Logistics"


def test_parse_llm_trip_response_accepts_fenced_json(tmp_path):
    service = make_service(tmp_path)
    content = """```json
{
  "summary": "A focused Paris plan.",
  "itinerary": [
    {
      "day": 1,
      "theme": "Food",
      "activities": [
        {
          "period": "Evening",
          "title": "Dinner",
          "reason": "Uses source context.",
          "source_titles": ["Paris Food Logistics"]
        }
      ]
    }
  ]
}
```"""

    response = service._parse_llm_trip_response(content, source_documents())

    assert response.generation_mode == "llm"
    assert response.itinerary[0].activities[0].period == "Evening"


def test_parse_llm_trip_response_rejects_invalid_json(tmp_path):
    service = make_service(tmp_path)

    with pytest.raises(GenerationError):
        service._parse_llm_trip_response("Here is your itinerary: not json", source_documents())


def test_parse_llm_trip_response_rejects_invalid_schema(tmp_path):
    service = make_service(tmp_path)
    content = """
    {
      "summary": "Missing itinerary."
    }
    """

    with pytest.raises(GenerationError):
        service._parse_llm_trip_response(content, source_documents())


def test_parse_llm_trip_response_normalizes_period_variants(tmp_path):
    service = make_service(tmp_path)
    content = """
    {
      "summary": "A focused Paris plan.",
      "itinerary": [
        {
          "day": 1,
          "theme": "Food",
          "activities": [
            {
              "period": "Breakfast",
              "title": "Bakery",
              "reason": "Uses source context.",
              "source_titles": ["Paris Food Logistics"]
            },
            {
              "period": "Lunch",
              "title": "Market",
              "reason": "Uses source context.",
              "source_titles": ["Paris Food Logistics"]
            },
            {
              "period": "Dinner",
              "title": "Bistro",
              "reason": "Uses source context.",
              "source_titles": ["Paris Food Logistics"]
            }
          ]
        }
      ]
    }
    """

    response = service._parse_llm_trip_response(content, source_documents())

    assert [activity.period for activity in response.itinerary[0].activities] == [
        "Morning",
        "Afternoon",
        "Evening",
    ]


def test_parse_llm_trip_response_fills_missing_source_titles(tmp_path):
    service = make_service(tmp_path)
    content = """
    {
      "summary": "A focused Paris plan.",
      "itinerary": [
        {
          "day": 1,
          "theme": "Food",
          "activities": [
            {
              "period": "Morning",
              "title": "Market walk",
              "reason": "Uses source context."
            }
          ]
        }
      ]
    }
    """

    response = service._parse_llm_trip_response(content, source_documents())

    assert response.itinerary[0].activities[0].source_titles == ["Paris Food Logistics"]


def test_format_feedback_entry_includes_activity_details(tmp_path):
    service = make_service(tmp_path)
    feedback = ActivityFeedbackRequest(
        destination="Tokyo",
        day=2,
        period="Afternoon",
        title="Daikanyama T-Site",
        rating="love",
        note="Great bookstore and cafe fit.",
        source_titles=["Saved Places Tokyo"],
    )

    entry = service._format_feedback_entry(feedback)

    assert "## Feedback: Tokyo day 2 Afternoon" in entry
    assert "- Activity: Daikanyama T-Site" in entry
    assert "- Rating: love" in entry
    assert "- Note: Great bookstore and cafe fit." in entry
    assert "- Sources: Saved Places Tokyo" in entry
