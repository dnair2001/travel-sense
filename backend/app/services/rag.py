import json
import re
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from langchain.prompts import ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import ValidationError

from app.config import Settings
from app.schemas import Activity, ActivityFeedbackRequest, DayPlan, RefinementRequest, SourceSnippet, TripRequest, TripResponse
from app.services.hash_embeddings import HashEmbeddings


class UnsupportedDestinationError(ValueError):
    def __init__(self, destination: str) -> None:
        self.destination = destination
        super().__init__(f"Unsupported destination: {destination}")


class GenerationError(ValueError):
    def __init__(self, message: str = "Unable to generate a valid itinerary.") -> None:
        super().__init__(message)


class TravelRAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=120,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
        )
        self._vectorstore: Optional[Chroma] = None

    @cached_property
    def embeddings(self):
        if self.settings.openai_api_key:
            return OpenAIEmbeddings(api_key=self.settings.openai_api_key)
        return HashEmbeddings()

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self.settings.chroma_path.mkdir(parents=True, exist_ok=True)
            self._vectorstore = Chroma(
                collection_name=self.settings.collection_name,
                persist_directory=str(self.settings.chroma_path),
                embedding_function=self.embeddings,
            )
        return self._vectorstore

    def load_source_documents(self) -> List[Document]:
        docs: List[Document] = []
        for city_dir in sorted(path for path in self.settings.data_dir.iterdir() if path.is_dir()):
            loader = DirectoryLoader(
                str(city_dir),
                glob="*.md",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
                show_progress=False,
            )
            city_docs = loader.load()
            for doc in city_docs:
                path = Path(doc.metadata.get("source", ""))
                if city_dir.name == "personal":
                    category = path.stem.replace("_", " ")
                    metadata = {
                        "city": "personal",
                        "category": category,
                        "scope": "personal",
                        "title": path.stem.replace("_", " ").title(),
                    }
                else:
                    category = path.stem.split("_", 1)[-1] if "_" in path.stem else "general"
                    metadata = {
                        "city": city_dir.name,
                        "category": category.replace("-", " "),
                        "scope": "destination",
                        "title": path.stem.replace("_", " ").title(),
                    }
                doc.metadata.update(
                    metadata
                )
            docs.extend(city_docs)
        return docs

    def split_documents(self, documents: List[Document]) -> List[Document]:
        chunks = self.text_splitter.split_documents(documents)
        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = index
        return chunks

    def rebuild_vectorstore(self) -> Dict[str, int]:
        documents = self.load_source_documents()
        chunks = self.split_documents(documents)
        self.vectorstore.delete_collection()
        self._vectorstore = Chroma(
            collection_name=self.settings.collection_name,
            persist_directory=str(self.settings.chroma_path),
            embedding_function=self.embeddings,
        )
        self._vectorstore.add_documents(chunks)
        unique_cities = {
            doc.metadata.get("city", "unknown")
            for doc in documents
            if doc.metadata.get("scope") == "destination"
        }
        personal_docs = sum(1 for doc in documents if doc.metadata.get("scope") == "personal")
        return {
            "documents": len(documents),
            "chunks": len(chunks),
            "cities": len(unique_cities),
            "personal_documents": personal_docs,
        }

    def ensure_index(self) -> None:
        collection = self.vectorstore._collection
        if collection.count() == 0:
            self.rebuild_vectorstore()

    def retrieve_documents(self, trip: TripRequest, extra_query: str = "") -> List[Document]:
        self.ensure_index()
        query = " ".join(
            part
            for part in [
                trip.destination,
                f"{trip.days} day trip",
                trip.budget,
                trip.travel_style,
                trip.pace,
                ", ".join(trip.interests),
                trip.constraints,
                extra_query,
            ]
            if part
        )
        city_key = self.normalize_city_key(trip.destination)
        destination_documents = self.vectorstore.similarity_search(
            query,
            k=6,
            filter={"$and": [{"scope": "destination"}, {"city": city_key}]},
        )
        saved_place_documents = self.vectorstore.similarity_search(
            query,
            k=3,
            filter={"$and": [{"scope": "personal"}, {"category": f"saved places {city_key}"}]},
        )
        personal_documents = self.vectorstore.similarity_search(
            query,
            k=6,
            filter={"scope": "personal"},
        )
        return self._dedupe_documents(destination_documents + saved_place_documents + personal_documents)

    def plan_trip(self, trip: TripRequest) -> TripResponse:
        documents = self.retrieve_documents(trip)
        self._ensure_destination_supported(trip.destination, documents)
        if self.settings.openai_api_key:
            return self._plan_with_llm(trip, documents)
        return self._plan_demo(trip, documents)

    def refine_trip(self, request: RefinementRequest) -> TripResponse:
        documents = self.retrieve_documents(request.trip, request.instruction)
        self._ensure_destination_supported(request.trip.destination, documents)
        if self.settings.openai_api_key:
            return self._refine_with_llm(request, documents)
        return self._refine_demo(request, documents)

    def record_activity_feedback(self, feedback: ActivityFeedbackRequest) -> Dict[str, str]:
        self.ensure_index()
        entry = self._format_feedback_entry(feedback)
        feedback_path = self.settings.data_dir / "personal" / "activity_feedback.md"
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        if not feedback_path.exists():
            feedback_path.write_text("# Activity Feedback\n\n", encoding="utf-8")
        with feedback_path.open("a", encoding="utf-8") as file:
            file.write(f"\n{entry}\n")

        self.vectorstore.add_documents(
            [
                Document(
                    page_content=entry,
                    metadata={
                        "city": "personal",
                        "category": "activity feedback",
                        "scope": "personal",
                        "title": "Activity Feedback",
                    },
                )
            ]
        )
        return {"message": "Activity feedback saved to personal travel memory."}

    def _plan_with_llm(self, trip: TripRequest, documents: List[Document]) -> TripResponse:
        context = self._serialize_context(documents)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are TravelSense, an itinerary planner. Use only the provided context. "
                    "Do not invent attractions or claims that are unsupported by the sources. "
                    "Return a JSON object with keys summary and itinerary. "
                    "itinerary must be a list of days, and each day must include day, theme, and activities. "
                    "Each activity must include period, title, reason, and source_titles.",
                ),
                (
                    "human",
                    "Trip request:\n"
                    "{trip_request}\n\n"
                    "Retrieved travel context:\n"
                    "{context}\n\n"
                    "Create a day-by-day itinerary for exactly {days} days.",
                ),
            ]
        )
        chain = prompt | ChatOpenAI(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            temperature=0.4,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = chain.invoke(
            {
                "trip_request": trip.model_dump_json(indent=2),
                "context": context,
                "days": trip.days,
            }
        )
        return self._parse_llm_trip_response(response.content, documents)

    def _refine_with_llm(self, request: RefinementRequest, documents: List[Document]) -> TripResponse:
        context = self._serialize_context(documents)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are revising an existing itinerary. Preserve the overall trip structure when possible, "
                    "but apply the user's refinement request. Use only the provided source context. "
                    "Return a JSON object with keys summary and itinerary. "
                    "Each itinerary day must include day, theme, and activities. "
                    "Each activity must include period, title, reason, and source_titles.",
                ),
                (
                    "human",
                    "Original trip request:\n"
                    "{trip_request}\n\n"
                    "Current summary:\n"
                    "{current_summary}\n\n"
                    "Current itinerary:\n"
                    "{current_itinerary}\n\n"
                    "Refinement request:\n"
                    "{instruction}\n\n"
                    "Retrieved travel context:\n"
                    "{context}",
                ),
            ]
        )
        chain = prompt | ChatOpenAI(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            temperature=0.4,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = chain.invoke(
            {
                "trip_request": request.trip.model_dump_json(indent=2),
                "current_summary": request.current_summary,
                "current_itinerary": json.dumps([day.model_dump() for day in request.current_itinerary], indent=2),
                "instruction": request.instruction,
                "context": context,
            }
        )
        return self._parse_llm_trip_response(response.content, documents)

    def _plan_demo(self, trip: TripRequest, documents: List[Document]) -> TripResponse:
        chunks = self._group_chunks_by_title(documents)
        summary = (
            f"A {trip.days}-day {trip.budget} trip to {trip.destination} tailored for "
            f"{', '.join(trip.interests) if trip.interests else 'general sightseeing'}, "
            f"with a {trip.pace} pace and a {trip.travel_style} travel style."
        )

        itinerary: List[DayPlan] = []
        titles = list(chunks.keys()) or ["Local Highlights"]
        for day_number in range(1, trip.days + 1):
            bucket = titles[(day_number - 1) % len(titles)]
            excerpt = chunks[bucket][0].page_content.strip().splitlines()[0]
            source_title = chunks[bucket][0].metadata.get("title", bucket)
            activities = [
                Activity(
                    period="Morning",
                    title=f"Explore {source_title}",
                    reason=f"Start with a source-backed area that matches the trip focus. {excerpt[:110]}",
                    source_titles=[source_title],
                ),
                Activity(
                    period="Afternoon",
                    title=f"Follow the {chunks[bucket][0].metadata.get('category', 'city')} recommendations",
                    reason="Use retrieved local guidance to keep the itinerary grounded in the destination docs.",
                    source_titles=[source_title],
                ),
                Activity(
                    period="Evening",
                    title="Flexible evening option",
                    reason="Leave room for a lower-pressure evening that still aligns with the retrieved neighborhood or food suggestions.",
                    source_titles=[source_title],
                ),
            ]
            itinerary.append(DayPlan(day=day_number, theme=bucket, activities=activities))

        return TripResponse(
            summary=summary,
            itinerary=itinerary,
            sources=self._build_sources(documents),
            generation_mode="demo",
        )

    def _refine_demo(self, request: RefinementRequest, documents: List[Document]) -> TripResponse:
        revised_days: List[DayPlan] = []
        for day in request.current_itinerary:
            updated_activities = []
            for activity in day.activities:
                updated_activities.append(
                    Activity(
                        period=activity.period,
                        title=activity.title,
                        reason=f"{activity.reason} Refinement applied: {request.instruction}.",
                        source_titles=activity.source_titles,
                    )
                )
            revised_days.append(DayPlan(day=day.day, theme=day.theme, activities=updated_activities))

        return TripResponse(
            summary=f"{request.current_summary} Updated to reflect: {request.instruction}.",
            itinerary=revised_days,
            sources=self._build_sources(documents),
            generation_mode="demo",
        )

    def _serialize_context(self, documents: List[Document]) -> str:
        blocks: List[str] = []
        for doc in documents:
            blocks.append(
                "\n".join(
                    [
                        f"Title: {doc.metadata.get('title', 'Unknown')}",
                        f"Scope: {doc.metadata.get('scope', 'destination')}",
                        f"City: {doc.metadata.get('city', 'unknown')}",
                        f"Category: {doc.metadata.get('category', 'general')}",
                        f"Content: {doc.page_content.strip()}",
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks)

    def _group_chunks_by_title(self, documents: List[Document]) -> Dict[str, List[Document]]:
        grouped: Dict[str, List[Document]] = {}
        for doc in documents:
            title = doc.metadata.get("title", "Untitled")
            grouped.setdefault(title, []).append(doc)
        return grouped

    def _build_sources(self, documents: List[Document]) -> List[SourceSnippet]:
        seen: Set[Tuple[str, str, str]] = set()
        sources: List[SourceSnippet] = []
        for doc in documents:
            key = (
                doc.metadata.get("title", "Unknown"),
                doc.metadata.get("city", "unknown"),
                doc.metadata.get("category", "general"),
            )
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                SourceSnippet(
                    title=key[0],
                    city=key[1],
                    category=key[2],
                    excerpt=doc.page_content.strip()[:220],
                )
            )
        return sources

    def _dedupe_documents(self, documents: List[Document]) -> List[Document]:
        seen: Set[Tuple[str, str, str, int]] = set()
        deduped: List[Document] = []
        for doc in documents:
            key = (
                doc.metadata.get("title", "Unknown"),
                doc.metadata.get("city", "unknown"),
                doc.metadata.get("category", "general"),
                doc.metadata.get("chunk_id", -1),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def _format_feedback_entry(self, feedback: ActivityFeedbackRequest) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        source_text = ", ".join(feedback.source_titles) if feedback.source_titles else "none"
        note = feedback.note.strip() or "none"
        return "\n".join(
            [
                f"## Feedback: {feedback.destination} day {feedback.day} {feedback.period}",
                "",
                f"- Recorded at: {timestamp}",
                f"- Destination: {feedback.destination}",
                f"- Activity: {feedback.title}",
                f"- Rating: {feedback.rating.replace('_', ' ')}",
                f"- Note: {note}",
                f"- Sources: {source_text}",
            ]
        )

    def _parse_llm_trip_response(self, content: str, documents: List[Document]) -> TripResponse:
        try:
            payload = json.loads(self._extract_json_content(content))
            payload = self._normalize_llm_payload(payload, documents)
            return TripResponse.model_validate(
                {
                    "summary": payload["summary"],
                    "itinerary": payload["itinerary"],
                    "sources": [source.model_dump() for source in self._build_sources(documents)],
                    "generation_mode": "llm",
                }
            )
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise GenerationError() from exc

    def _extract_json_content(self, content: str) -> str:
        stripped = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return stripped

    def _normalize_llm_payload(self, payload: dict, documents: List[Document]) -> dict:
        source_titles = [source.title for source in self._build_sources(documents)]
        fallback_source_titles = source_titles[:1]
        for day in payload.get("itinerary", []):
            activities = day.get("activities", [])
            for index, activity in enumerate(activities):
                activity["period"] = self._normalize_activity_period(activity.get("period"), index)
                if not activity.get("source_titles"):
                    activity["source_titles"] = fallback_source_titles
        return payload

    def _normalize_activity_period(self, period: object, index: int) -> str:
        if isinstance(period, str):
            normalized = period.strip().lower()
            if normalized in {"morning", "am"} or "morning" in normalized or "breakfast" in normalized:
                return "Morning"
            if (
                normalized in {"afternoon", "pm"}
                or "afternoon" in normalized
                or "lunch" in normalized
                or "midday" in normalized
            ):
                return "Afternoon"
            if "evening" in normalized or "night" in normalized or "dinner" in normalized:
                return "Evening"
        return ["Morning", "Afternoon", "Evening"][min(index, 2)]

    def _ensure_destination_supported(self, destination: str, documents: List[Document]) -> None:
        city_key = self.normalize_city_key(destination)
        if not any(
            doc.metadata.get("scope") == "destination" and doc.metadata.get("city") == city_key
            for doc in documents
        ):
            raise UnsupportedDestinationError(destination)

    def normalize_city_key(self, destination: str) -> str:
        normalized = destination.strip().lower()
        aliases = {
            "new york": "nyc",
            "new york city": "nyc",
            "nyc": "nyc",
            "tokyo": "tokyo",
            "paris": "paris",
        }
        return aliases.get(normalized, normalized.replace(" ", "-"))
