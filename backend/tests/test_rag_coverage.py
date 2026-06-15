"""Tests targeting uncovered paths in app/services/rag.py."""

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.config import Settings
from app.schemas import (
    Activity,
    ActivityFeedbackRequest,
    DayPlan,
    RefinementRequest,
    TripRequest,
    TripResponse,
)
from app.services.rag import GenerationError, TravelRAGService


def _make_service(tmp_path, *, isolated_data=False):
    settings = Settings(
        openai_api_key=None,
        chroma_dir=str(tmp_path / "chroma"),
        collection_name="test-coverage-docs",
    )
    if isolated_data:
        # Point data_dir to an isolated tmp location for clean tests
        object.__setattr__(settings, "_isolated_data_dir", tmp_path / "data")
        original_data_dir = type(settings).data_dir
        type(settings).data_dir = property(lambda self: self._isolated_data_dir)
    return TravelRAGService(settings)


def _source_docs():
    return [
        Document(
            page_content="Paris food guidance.\nGreat bakeries on the Left Bank.",
            metadata={
                "title": "Paris Food Logistics",
                "city": "paris",
                "category": "food_logistics",
                "scope": "destination",
            },
        ),
        Document(
            page_content="Tokyo transit tips.\nUse a Suica card for trains.",
            metadata={
                "title": "Tokyo Transit Guide",
                "city": "tokyo",
                "category": "transit",
                "scope": "destination",
            },
        ),
    ]


# --- _serialize_context ---

def test_serialize_context_formats_documents_with_metadata(tmp_path):
    service = _make_service(tmp_path)
    docs = _source_docs()

    result = service._serialize_context(docs)

    assert "Title: Paris Food Logistics" in result
    assert "Scope: destination" in result
    assert "City: paris" in result
    assert "Category: food_logistics" in result
    assert "Content: Paris food guidance." in result
    assert "---" in result
    assert "Title: Tokyo Transit Guide" in result


def test_serialize_context_handles_empty_list(tmp_path):
    service = _make_service(tmp_path)
    assert service._serialize_context([]) == ""


def test_serialize_context_handles_missing_metadata(tmp_path):
    service = _make_service(tmp_path)
    docs = [Document(page_content="No metadata here.", metadata={})]

    result = service._serialize_context(docs)

    assert "Title: Unknown" in result
    assert "Scope: destination" in result
    assert "City: unknown" in result
    assert "Category: general" in result


# --- _normalize_activity_period ---

def test_normalize_activity_period_fallback_uses_index(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period(None, 0) == "Morning"
    assert service._normalize_activity_period(None, 1) == "Afternoon"
    assert service._normalize_activity_period(None, 2) == "Evening"
    assert service._normalize_activity_period(None, 5) == "Evening"


def test_normalize_activity_period_numeric_input(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period(42, 0) == "Morning"
    assert service._normalize_activity_period(42, 1) == "Afternoon"


def test_normalize_activity_period_recognizes_am_pm(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period("am", 2) == "Morning"
    assert service._normalize_activity_period("pm", 0) == "Afternoon"


def test_normalize_activity_period_recognizes_midday(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period("midday", 0) == "Afternoon"


def test_normalize_activity_period_recognizes_night(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period("night", 0) == "Evening"


def test_normalize_activity_period_unknown_string_falls_back_to_index(tmp_path):
    service = _make_service(tmp_path)
    assert service._normalize_activity_period("brunch", 0) == "Morning"
    assert service._normalize_activity_period("teatime", 1) == "Afternoon"


# --- ensure_index when collection already populated ---

def test_ensure_index_rebuilds_when_collection_is_empty(tmp_path):
    """Covers line 126: rebuild_vectorstore() called from ensure_index."""
    service = _make_service(tmp_path)
    assert service.vectorstore._collection.count() == 0

    service.ensure_index()

    assert service.vectorstore._collection.count() > 0


def test_ensure_index_skips_rebuild_when_collection_has_data(tmp_path):
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()
    count_before = service.vectorstore._collection.count()

    service.ensure_index()

    assert service.vectorstore._collection.count() == count_before


# --- record_activity_feedback ---

def test_record_activity_feedback_creates_file_when_missing(tmp_path):
    """Covers line 182: feedback_path.write_text when file doesn't exist."""
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()

    # Remove the feedback file if it was created during rebuild
    feedback_path = service.settings.data_dir / "personal" / "activity_feedback.md"
    if feedback_path.exists():
        feedback_path.unlink()

    feedback = ActivityFeedbackRequest(
        destination="Paris",
        day=1,
        period="Morning",
        title="New Spot",
        rating="love",
        note="First feedback ever.",
        source_titles=[],
    )

    service.record_activity_feedback(feedback)

    assert feedback_path.exists()
    content = feedback_path.read_text(encoding="utf-8")
    assert content.startswith("# Activity Feedback")
    assert "New Spot" in content


def test_record_activity_feedback_persists_to_file_and_vectorstore(tmp_path):
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()
    count_before = service.vectorstore._collection.count()

    feedback = ActivityFeedbackRequest(
        destination="Paris",
        day=1,
        period="Morning",
        title="Café de Flore",
        rating="love",
        note="Amazing atmosphere.",
        source_titles=["Paris Food Logistics"],
    )

    result = service.record_activity_feedback(feedback)

    assert result["message"] == "Activity feedback saved to personal travel memory."
    feedback_path = service.settings.data_dir / "personal" / "activity_feedback.md"
    assert feedback_path.exists()
    content = feedback_path.read_text(encoding="utf-8")
    assert "Café de Flore" in content
    assert "love" in content
    assert service.vectorstore._collection.count() == count_before + 1


def test_record_activity_feedback_appends_to_existing_file(tmp_path):
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()

    feedback1 = ActivityFeedbackRequest(
        destination="Paris",
        day=1,
        period="Morning",
        title="Café de Flore",
        rating="love",
        note="",
        source_titles=[],
    )
    feedback2 = ActivityFeedbackRequest(
        destination="Tokyo",
        day=2,
        period="Evening",
        title="Ramen Alley",
        rating="not_for_me",
        note="Too crowded.",
        source_titles=["Tokyo Transit Guide"],
    )

    service.record_activity_feedback(feedback1)
    service.record_activity_feedback(feedback2)

    feedback_path = service.settings.data_dir / "personal" / "activity_feedback.md"
    content = feedback_path.read_text(encoding="utf-8")
    assert "Café de Flore" in content
    assert "Ramen Alley" in content
    assert "not for me" in content


def test_format_feedback_entry_handles_empty_note_and_sources(tmp_path):
    service = _make_service(tmp_path)
    feedback = ActivityFeedbackRequest(
        destination="NYC",
        day=3,
        period="Afternoon",
        title="Central Park",
        rating="too_much_walking",
        note="",
        source_titles=[],
    )

    entry = service._format_feedback_entry(feedback)

    assert "- Note: none" in entry
    assert "- Sources: none" in entry
    assert "- Rating: too much walking" in entry


# --- _plan_with_llm (mocked) ---

def test_plan_with_llm_returns_trip_response(tmp_path):
    service = _make_service(tmp_path)
    service.settings.openai_api_key = "fake-key"

    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )
    docs = _source_docs()
    llm_json = json.dumps({
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
                        "source_titles": ["Paris Food Logistics"],
                    }
                ],
            }
        ],
    })

    mock_response = MagicMock()
    mock_response.content = llm_json

    with patch("app.services.rag.ChatOpenAI") as MockChatOpenAI:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        MockChatOpenAI.return_value = mock_chain
        # ChatPromptTemplate | ChatOpenAI → need to patch the __or__ result
        with patch("app.services.rag.ChatPromptTemplate") as MockPrompt:
            mock_prompt_instance = MagicMock()
            MockPrompt.from_messages.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(return_value=mock_chain)

            response = service._plan_with_llm(trip, docs)

    assert isinstance(response, TripResponse)
    assert response.generation_mode == "llm"
    assert response.summary == "A focused Paris plan."


# --- _refine_with_llm (mocked) ---

def test_refine_with_llm_returns_trip_response(tmp_path):
    service = _make_service(tmp_path)
    service.settings.openai_api_key = "fake-key"

    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )
    request = RefinementRequest(
        trip=trip,
        current_summary="Original Paris plan.",
        current_itinerary=[
            DayPlan(
                day=1,
                theme="Food",
                activities=[
                    Activity(
                        period="Morning",
                        title="Market walk",
                        reason="Uses source context.",
                        source_titles=["Paris Food Logistics"],
                    )
                ],
            )
        ],
        instruction="make it quieter",
    )
    docs = _source_docs()
    llm_json = json.dumps({
        "summary": "Quieter Paris plan.",
        "itinerary": [
            {
                "day": 1,
                "theme": "Quiet Food",
                "activities": [
                    {
                        "period": "Morning",
                        "title": "Bakery stroll",
                        "reason": "A quiet morning walk.",
                        "source_titles": ["Paris Food Logistics"],
                    }
                ],
            }
        ],
    })

    mock_response = MagicMock()
    mock_response.content = llm_json

    with patch("app.services.rag.ChatOpenAI") as MockChatOpenAI:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        MockChatOpenAI.return_value = mock_chain
        with patch("app.services.rag.ChatPromptTemplate") as MockPrompt:
            mock_prompt_instance = MagicMock()
            MockPrompt.from_messages.return_value = mock_prompt_instance
            mock_prompt_instance.__or__ = MagicMock(return_value=mock_chain)

            response = service._refine_with_llm(request, docs)

    assert isinstance(response, TripResponse)
    assert response.generation_mode == "llm"
    assert response.summary == "Quieter Paris plan."


# --- plan_trip / refine_trip LLM branch routing ---

def test_plan_trip_delegates_to_llm_when_api_key_set(tmp_path):
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()
    service.settings.openai_api_key = "fake-key"

    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )

    fake_response = TripResponse(
        summary="LLM Paris",
        itinerary=[
            DayPlan(
                day=1,
                theme="Food",
                activities=[
                    Activity(
                        period="Morning",
                        title="LLM suggestion",
                        reason="From LLM.",
                        source_titles=["Paris Food Logistics"],
                    )
                ],
            )
        ],
        sources=[],
        generation_mode="llm",
    )

    with patch.object(service, "_plan_with_llm", return_value=fake_response) as mock_llm:
        response = service.plan_trip(trip)

    mock_llm.assert_called_once()
    assert response.generation_mode == "llm"


def test_refine_trip_delegates_to_llm_when_api_key_set(tmp_path):
    service = _make_service(tmp_path)
    service.rebuild_vectorstore()
    service.settings.openai_api_key = "fake-key"

    trip = TripRequest(
        destination="Paris",
        days=1,
        budget="mid-range",
        interests=["food"],
        travel_style="solo",
        pace="balanced",
        constraints="",
    )
    request = RefinementRequest(
        trip=trip,
        current_summary="Original.",
        current_itinerary=[
            DayPlan(
                day=1,
                theme="Food",
                activities=[
                    Activity(
                        period="Morning",
                        title="Walk",
                        reason="Original reason.",
                        source_titles=["Guide"],
                    )
                ],
            )
        ],
        instruction="add museums",
    )

    fake_response = TripResponse(
        summary="LLM Refined",
        itinerary=request.current_itinerary,
        sources=[],
        generation_mode="llm",
    )

    with patch.object(service, "_refine_with_llm", return_value=fake_response) as mock_llm:
        response = service.refine_trip(request)

    mock_llm.assert_called_once()
    assert response.generation_mode == "llm"


# --- normalize_city_key ---

def test_normalize_city_key_aliases(tmp_path):
    service = _make_service(tmp_path)
    assert service.normalize_city_key("New York") == "nyc"
    assert service.normalize_city_key("New York City") == "nyc"
    assert service.normalize_city_key("NYC") == "nyc"
    assert service.normalize_city_key("Tokyo") == "tokyo"
    assert service.normalize_city_key("Paris") == "paris"


def test_normalize_city_key_unknown_city(tmp_path):
    service = _make_service(tmp_path)
    assert service.normalize_city_key("San Francisco") == "san-francisco"
    assert service.normalize_city_key("  Rio de Janeiro  ") == "rio-de-janeiro"


# --- _dedupe_documents ---

def test_dedupe_documents_removes_exact_duplicates(tmp_path):
    service = _make_service(tmp_path)
    doc = Document(
        page_content="Duplicate content.",
        metadata={"title": "Guide", "city": "paris", "category": "food", "chunk_id": 1},
    )

    result = service._dedupe_documents([doc, doc, doc])

    assert len(result) == 1


def test_dedupe_documents_keeps_distinct_chunks(tmp_path):
    service = _make_service(tmp_path)
    doc_a = Document(
        page_content="Chunk A.",
        metadata={"title": "Guide", "city": "paris", "category": "food", "chunk_id": 1},
    )
    doc_b = Document(
        page_content="Chunk B.",
        metadata={"title": "Guide", "city": "paris", "category": "food", "chunk_id": 2},
    )

    result = service._dedupe_documents([doc_a, doc_b])

    assert len(result) == 2


# --- _group_chunks_by_title ---

def test_group_chunks_by_title(tmp_path):
    service = _make_service(tmp_path)
    docs = _source_docs()

    grouped = service._group_chunks_by_title(docs)

    assert "Paris Food Logistics" in grouped
    assert "Tokyo Transit Guide" in grouped
    assert len(grouped["Paris Food Logistics"]) == 1


# --- _build_sources deduplication ---

def test_build_sources_deduplicates(tmp_path):
    service = _make_service(tmp_path)
    doc = _source_docs()[0]

    sources = service._build_sources([doc, doc, doc])

    assert len(sources) == 1
    assert sources[0].title == "Paris Food Logistics"
