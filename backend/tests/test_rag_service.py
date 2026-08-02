import pytest
from langchain_core.documents import Document

from app.config import Settings
from app.schemas import Activity, DayPlan, RefinementRequest, TripRequest
from app.services.rag import GenerationError, TravelRAGService, UnsupportedDestinationError

TEST_USER = "test-user"


def make_service(tmp_path, legacy_personal_owner_user_id=TEST_USER):
    settings = Settings(
        openai_api_key=None,
        chroma_dir=str(tmp_path / "chroma"),
        collection_name="test-travel-sense-docs",
        legacy_personal_owner_user_id=legacy_personal_owner_user_id,
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
    service.vectorstore.add_documents(
        [
            Document(
                page_content="A user-uploaded Paris cafe guide.",
                metadata={
                    "title": "My Paris Cafe Guide",
                    "city": "paris",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": TEST_USER,
                },
            )
        ],
        ids=[f"{TEST_USER}-paris-0"],
    )
    trip = TripRequest(
        destination="Paris",
        days=2,
        budget="mid-range",
        interests=["food", "art"],
        travel_style="couple",
        pace="balanced",
        constraints="near transit",
    )

    documents = service.retrieve_documents(trip, TEST_USER)

    assert documents
    destination_documents = [doc for doc in documents if doc.metadata["scope"] == "destination"]
    personal_documents = [doc for doc in documents if doc.metadata["scope"] == "personal"]
    # Only the user's own uploaded Paris content comes back — the seeded
    # "Paris Art Cafes"/"Paris Food Logistics" public guides are excluded.
    assert {doc.metadata["title"] for doc in destination_documents} == {"My Paris Cafe Guide"}
    assert not any(doc.metadata.get("owner_scope") == "public" for doc in documents)
    assert personal_documents


def test_plan_trip_demo_uses_retrieved_sources(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    service.vectorstore.add_documents(
        [
            Document(
                page_content="A user-uploaded Tokyo food crawl guide.",
                metadata={
                    "title": "My Tokyo Food Crawl",
                    "city": "tokyo",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": TEST_USER,
                },
            )
        ],
        ids=[f"{TEST_USER}-tokyo-0"],
    )
    trip = TripRequest(
        destination="Tokyo",
        days=3,
        budget="budget",
        interests=["food", "transit"],
        travel_style="friends",
        pace="fast",
        constraints="avoid taxis",
    )

    response = service.plan_trip(trip, TEST_USER)

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

    documents = service.retrieve_documents(trip, TEST_USER)
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
        service.plan_trip(trip, TEST_USER)

    assert exc_info.value.destination == "Atlantis"


def test_refine_trip_demo_preserves_days_and_applies_instruction(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    service.vectorstore.add_documents(
        [
            Document(
                page_content="A user-uploaded NYC neighborhoods guide.",
                metadata={
                    "title": "My NYC Neighborhoods Guide",
                    "city": "nyc",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": TEST_USER,
                },
            )
        ],
        ids=[f"{TEST_USER}-nyc-0"],
    )
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

    response = service.refine_trip(request, TEST_USER)

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
        service.refine_trip(request, TEST_USER)

    assert exc_info.value.destination == "Atlantis"


def test_retrieve_documents_scopes_private_docs_to_owning_user(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    service.vectorstore.add_documents(
        [
            Document(
                page_content="User A's favorite Lisbon miradouros.",
                metadata={
                    "title": "User A Lisbon Notes",
                    "city": "lisbon",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": "user-a",
                },
            ),
            Document(
                page_content="User B's favorite Lisbon miradouros.",
                metadata={
                    "title": "User B Lisbon Notes",
                    "city": "lisbon",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": "user-b",
                },
            ),
        ],
        ids=["user-a-lisbon-0", "user-b-lisbon-0"],
    )
    trip = TripRequest(
        destination="Lisbon",
        days=1,
        budget="mid-range",
        interests=["miradouros"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )

    user_a_documents = service.retrieve_documents(trip, "user-a")
    user_b_documents = service.retrieve_documents(trip, "user-b")

    user_a_titles = {doc.metadata["title"] for doc in user_a_documents}
    user_b_titles = {doc.metadata["title"] for doc in user_b_documents}
    assert "User A Lisbon Notes" in user_a_titles
    assert "User B Lisbon Notes" not in user_a_titles
    assert "User B Lisbon Notes" in user_b_titles
    assert "User A Lisbon Notes" not in user_b_titles


def test_public_seed_content_is_excluded_from_retrieval(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )

    documents = service.retrieve_documents(trip, TEST_USER)

    assert not any(doc.metadata.get("owner_scope") == "public" for doc in documents)


def test_plan_trip_rejects_destination_with_only_seed_content(tmp_path):
    # Paris has seeded public guide docs but this user hasn't uploaded
    # anything for it, so it should behave like an unsupported destination.
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )

    with pytest.raises(UnsupportedDestinationError):
        service.plan_trip(trip, TEST_USER)


def test_rebuild_vectorstore_does_not_delete_user_documents(tmp_path):
    service = make_service(tmp_path)
    service.rebuild_vectorstore()
    service.vectorstore.add_documents(
        [
            Document(
                page_content="A private Lisbon note.",
                metadata={
                    "title": "Private Lisbon Note",
                    "city": "lisbon",
                    "category": "blog",
                    "scope": "destination",
                    "owner_scope": "user",
                    "user_id": "user-a",
                },
            )
        ],
        ids=["user-a-lisbon-0"],
    )

    service.rebuild_vectorstore()

    stored = service.vectorstore._collection.get(ids=["user-a-lisbon-0"])
    assert stored["ids"] == ["user-a-lisbon-0"]


def test_personal_data_excluded_without_legacy_owner_configured(tmp_path):
    service = make_service(tmp_path, legacy_personal_owner_user_id=None)

    result = service.rebuild_vectorstore()

    assert result["personal_documents"] == 0
    trip = TripRequest(
        destination="Tokyo",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )
    documents = service.retrieve_documents(trip, TEST_USER)
    assert not any(doc.metadata.get("scope") == "personal" for doc in documents)


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
