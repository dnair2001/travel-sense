import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx
import trafilatura
from langchain_core.documents import Document
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.schemas import IngestedSource, SourceType
from app.services.rag import TravelRAGService

FETCH_TIMEOUT_SECONDS = 15.0
FETCH_USER_AGENT = (
    "Mozilla/5.0 (compatible; TravelSenseBot/1.0; +https://travelsense.app)"
)


class IngestionError(ValueError):
    pass


def detect_source_type(url: str) -> SourceType:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("youtube.com") or host.endswith("youtu.be"):
        return "youtube"
    return "blog"


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host.endswith("youtu.be"):
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id

    if host.endswith("youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id:
                return video_id
        for prefix in ("/shorts/", "/embed/", "/live/"):
            if parsed.path.startswith(prefix):
                video_id = parsed.path[len(prefix):].split("/")[0]
                if video_id:
                    return video_id

    raise IngestionError(f"Could not find a YouTube video id in '{url}'.")


class SourceIngestionService:
    def __init__(self, rag_service: TravelRAGService) -> None:
        self.rag = rag_service

    def ingest(self, user_id: str, destination: str, url: str) -> Dict[str, object]:
        source_type = detect_source_type(url)
        if source_type == "youtube":
            text, title = self._fetch_youtube_transcript(url)
        else:
            text, title = self._fetch_blog_article(url)

        city_key = self.rag.normalize_city_key(destination)
        document = Document(
            page_content=text,
            metadata={
                "city": city_key,
                "category": source_type,
                "scope": "destination",
                "title": title,
                "owner_scope": "user",
                "user_id": user_id,
                "source_url": url,
                "source_type": source_type,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        chunks = self.rag.split_documents([document])
        if not chunks:
            raise IngestionError(f"No usable text was extracted from '{url}'.")

        ids = [self._chunk_id(user_id, url, index) for index in range(len(chunks))]

        # Delete-then-add rather than relying solely on upsert-by-id: a
        # re-ingested page that now chunks shorter than before would
        # otherwise leave stale trailing chunks behind.
        self.rag.vectorstore._collection.delete(
            where={"$and": [{"user_id": user_id}, {"source_url": url}]}
        )
        self.rag.vectorstore.add_documents(chunks, ids=ids)

        return {
            "url": url,
            "source_type": source_type,
            "title": title,
            "chunks_indexed": len(chunks),
            "city": city_key,
        }

    def list_sources(self, user_id: str, destination: Optional[str] = None) -> List[IngestedSource]:
        where: Dict[str, object] = {"user_id": user_id}
        if destination is not None:
            where = {
                "$and": [
                    {"user_id": user_id},
                    {"city": self.rag.normalize_city_key(destination)},
                ]
            }
        result = self.rag.vectorstore.get(where=where)
        grouped: Dict[str, Dict[str, object]] = {}
        for metadata in result.get("metadatas", []):
            url = metadata.get("source_url")
            if url is None:
                continue
            entry = grouped.setdefault(
                url,
                {
                    "url": url,
                    "title": metadata.get("title", url),
                    "source_type": metadata.get("source_type", "blog"),
                    "city": metadata.get("city", "unknown"),
                    "ingested_at": metadata.get("ingested_at", ""),
                    "chunk_count": 0,
                },
            )
            entry["chunk_count"] = int(entry["chunk_count"]) + 1
        return [IngestedSource.model_validate(entry) for entry in grouped.values()]

    def delete_source(self, user_id: str, url: str) -> None:
        self.rag.vectorstore._collection.delete(
            where={"$and": [{"user_id": user_id}, {"source_url": url}]}
        )

    def _chunk_id(self, user_id: str, url: str, index: int) -> str:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        return f"user:{user_id}:{url_hash}:{index}"

    def _fetch_blog_article(self, url: str) -> tuple[str, str]:
        try:
            response = httpx.get(
                url,
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": FETCH_USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IngestionError(f"Could not fetch '{url}': {exc}") from exc

        extracted = trafilatura.extract(
            response.text,
            with_metadata=True,
            output_format="json",
            url=url,
        )
        if not extracted:
            raise IngestionError(f"Could not extract article text from '{url}'.")

        payload = json.loads(extracted)
        text = (payload.get("text") or "").strip()
        if not text:
            raise IngestionError(f"Could not extract article text from '{url}'.")
        title = payload.get("title") or url
        return text, title

    def _fetch_youtube_transcript(self, url: str) -> tuple[str, str]:
        video_id = extract_youtube_video_id(url)
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id)
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
            raise IngestionError(
                f"No captions are available for this video ({url})."
            ) from exc
        text = " ".join(segment.get("text", "") for segment in segments).strip()
        if not text:
            raise IngestionError(f"No captions are available for this video ({url}).")
        return text, f"YouTube video {video_id}"
