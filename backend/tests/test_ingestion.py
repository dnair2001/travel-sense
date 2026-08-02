import json

import pytest

from app.config import Settings
from app.services.ingestion import (
    IngestionError,
    SourceIngestionService,
    detect_source_type,
    extract_youtube_video_id,
)
from app.services.rag import TravelRAGService

TEST_USER = "test-user"


def make_ingestion_service(tmp_path):
    settings = Settings(
        openai_api_key=None,
        chroma_dir=str(tmp_path / "chroma"),
        collection_name="test-travel-sense-docs",
    )
    rag_service = TravelRAGService(settings)
    return SourceIngestionService(rag_service)


class FakeHttpResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeFetchedTranscript:
    def __init__(self, raw_data) -> None:
        self._raw_data = raw_data

    def to_raw_data(self):
        return self._raw_data


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc123", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://www.youtube.com/shorts/abc123", "youtube"),
        ("https://example.com/tokyo-food-guide", "blog"),
        ("https://myblog.travel/paris/cafes", "blog"),
    ],
)
def test_detect_source_type(url, expected):
    assert detect_source_type(url) == expected


@pytest.mark.parametrize(
    "url,expected_id",
    [
        ("https://www.youtube.com/watch?v=abc123", "abc123"),
        ("https://www.youtube.com/watch?v=abc123&t=30s", "abc123"),
        ("https://youtu.be/abc123", "abc123"),
        ("https://youtu.be/abc123?si=xyz", "abc123"),
        ("https://www.youtube.com/shorts/abc123", "abc123"),
        ("https://www.youtube.com/embed/abc123", "abc123"),
    ],
)
def test_extract_youtube_video_id(url, expected_id):
    assert extract_youtube_video_id(url) == expected_id


def test_extract_youtube_video_id_raises_on_malformed_url():
    with pytest.raises(IngestionError):
        extract_youtube_video_id("https://www.youtube.com/")


def test_ingest_blog_article(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)

    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse("<html><body>Some Lisbon guidance.</body></html>"),
    )
    monkeypatch.setattr(
        "app.services.ingestion.trafilatura.extract",
        lambda *args, **kwargs: json.dumps({"title": "Lisbon Guide", "text": "Great miradouros in Lisbon."}),
    )

    result = service.ingest(TEST_USER, "Lisbon", "https://example.com/lisbon-guide")

    assert result["source_type"] == "blog"
    assert result["title"] == "Lisbon Guide"
    assert result["chunks_indexed"] == 1
    assert result["city"] == "lisbon"

    sources = service.list_sources(TEST_USER, "Lisbon")
    assert len(sources) == 1
    assert sources[0].url == "https://example.com/lisbon-guide"
    assert sources[0].chunk_count == 1


def test_ingest_blog_article_raises_on_empty_extraction(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)

    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse("<html></html>"),
    )
    monkeypatch.setattr("app.services.ingestion.trafilatura.extract", lambda *args, **kwargs: None)

    with pytest.raises(IngestionError):
        service.ingest(TEST_USER, "Lisbon", "https://example.com/empty")


def test_ingest_youtube_video(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)

    monkeypatch.setattr(
        "app.services.ingestion.YouTubeTranscriptApi.fetch",
        lambda self, video_id, *args, **kwargs: FakeFetchedTranscript(
            [{"text": "Welcome to"}, {"text": "Lisbon's best miradouros."}]
        ),
    )

    result = service.ingest(TEST_USER, "Lisbon", "https://youtu.be/abc123")

    assert result["source_type"] == "youtube"
    assert result["chunks_indexed"] == 1


def test_ingest_youtube_video_raises_when_no_transcript(tmp_path, monkeypatch):
    from youtube_transcript_api._errors import TranscriptsDisabled

    service = make_ingestion_service(tmp_path)

    def raise_disabled(self, video_id, *args, **kwargs):
        raise TranscriptsDisabled(video_id)

    monkeypatch.setattr("app.services.ingestion.YouTubeTranscriptApi.fetch", raise_disabled)

    with pytest.raises(IngestionError):
        service.ingest(TEST_USER, "Lisbon", "https://youtu.be/abc123")


def test_reingest_url_replaces_stale_chunks(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)
    long_text = "Lisbon miradouros are wonderful. " * 60  # multiple chunks
    short_text = "Lisbon miradouros."  # a single, much shorter chunk

    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse("<html></html>"),
    )
    monkeypatch.setattr(
        "app.services.ingestion.trafilatura.extract",
        lambda *args, **kwargs: json.dumps({"title": "Lisbon Guide", "text": long_text}),
    )

    first_result = service.ingest(TEST_USER, "Lisbon", "https://example.com/lisbon-guide")
    assert first_result["chunks_indexed"] > 1

    monkeypatch.setattr(
        "app.services.ingestion.trafilatura.extract",
        lambda *args, **kwargs: json.dumps({"title": "Lisbon Guide", "text": short_text}),
    )
    second_result = service.ingest(TEST_USER, "Lisbon", "https://example.com/lisbon-guide")
    assert second_result["chunks_indexed"] == 1

    sources = service.list_sources(TEST_USER, "Lisbon")
    assert len(sources) == 1
    assert sources[0].chunk_count == 1


def test_delete_source_removes_chunks(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)
    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse("<html></html>"),
    )
    monkeypatch.setattr(
        "app.services.ingestion.trafilatura.extract",
        lambda *args, **kwargs: json.dumps({"title": "Lisbon Guide", "text": "Great miradouros."}),
    )
    service.ingest(TEST_USER, "Lisbon", "https://example.com/lisbon-guide")

    service.delete_source(TEST_USER, "https://example.com/lisbon-guide")

    assert service.list_sources(TEST_USER, "Lisbon") == []


def test_list_sources_scoped_to_user(tmp_path, monkeypatch):
    service = make_ingestion_service(tmp_path)
    monkeypatch.setattr(
        "app.services.ingestion.httpx.get",
        lambda *args, **kwargs: FakeHttpResponse("<html></html>"),
    )
    monkeypatch.setattr(
        "app.services.ingestion.trafilatura.extract",
        lambda *args, **kwargs: json.dumps({"title": "Lisbon Guide", "text": "Great miradouros."}),
    )
    service.ingest("user-a", "Lisbon", "https://example.com/lisbon-guide")

    assert service.list_sources("user-a", "Lisbon") != []
    assert service.list_sources("user-b", "Lisbon") == []
