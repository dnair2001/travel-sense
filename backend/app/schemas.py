from typing import Literal

from pydantic import BaseModel, Field


BudgetLevel = Literal["budget", "mid-range", "luxury"]
PaceLevel = Literal["slow", "balanced", "fast"]


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=2)
    days: int = Field(..., ge=1, le=14)
    budget: BudgetLevel
    interests: list[str] = Field(default_factory=list)
    travel_style: str = Field(default="general")
    pace: PaceLevel = "balanced"
    constraints: str = ""


class SourceSnippet(BaseModel):
    title: str
    city: str
    category: str
    excerpt: str


class Activity(BaseModel):
    period: Literal["Morning", "Afternoon", "Evening"]
    title: str
    reason: str
    source_titles: list[str]


class DayPlan(BaseModel):
    day: int
    theme: str
    activities: list[Activity]


class TripResponse(BaseModel):
    summary: str
    itinerary: list[DayPlan]
    sources: list[SourceSnippet]
    generation_mode: Literal["llm", "demo"]


class RefinementRequest(BaseModel):
    trip: TripRequest
    current_summary: str
    current_itinerary: list[DayPlan]
    instruction: str = Field(..., min_length=3)


SourceType = Literal["blog", "youtube"]


class SourceIngestRequest(BaseModel):
    destination: str = Field(..., min_length=2)
    url: str = Field(..., min_length=1)


class SourceIngestResponse(BaseModel):
    url: str
    source_type: SourceType
    title: str
    chunks_indexed: int
    city: str


class IngestedSource(BaseModel):
    url: str
    title: str
    source_type: SourceType
    city: str
    ingested_at: str
    chunk_count: int


class SourceListResponse(BaseModel):
    sources: list[IngestedSource]


class SourceDeleteRequest(BaseModel):
    url: str = Field(..., min_length=1)


class SourceDeleteResponse(BaseModel):
    deleted: bool


class GeocodeResponse(BaseModel):
    lat: float
    lng: float
    label: str
    is_approximate: bool = False


class DirectionsRequest(BaseModel):
    # Ordered (lat, lng) pairs to route through, in visiting order.
    coordinates: list[tuple[float, float]] = Field(..., min_length=2)


class RouteLeg(BaseModel):
    distance_m: float
    walking_duration_s: float
    driving_duration_s: float


class RouteResponse(BaseModel):
    geometry: dict
    distance_m: float
    walking_duration_s: float
    driving_duration_s: float
    legs: list[RouteLeg]
