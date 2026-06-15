from typing import Literal

from pydantic import BaseModel, Field


BudgetLevel = Literal["budget", "mid-range", "luxury"]
PaceLevel = Literal["slow", "balanced", "fast"]
FeedbackRating = Literal["love", "not_for_me", "too_expensive", "too_much_walking", "too_touristy"]


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=2, max_length=100)
    days: int = Field(..., ge=1, le=14)
    budget: BudgetLevel
    interests: list[str] = Field(default_factory=list, max_length=20)
    travel_style: str = Field(default="general", max_length=100)
    pace: PaceLevel = "balanced"
    constraints: str = Field(default="", max_length=1000)


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
    current_summary: str = Field(..., max_length=2000)
    current_itinerary: list[DayPlan] = Field(..., max_length=14)
    instruction: str = Field(..., min_length=3, max_length=1000)


class ActivityFeedbackRequest(BaseModel):
    destination: str = Field(..., min_length=2, max_length=100)
    day: int = Field(..., ge=1, le=14)
    period: Literal["Morning", "Afternoon", "Evening"]
    title: str = Field(..., min_length=1, max_length=200)
    rating: FeedbackRating
    note: str = Field(default="", max_length=1000)
    source_titles: list[str] = Field(default_factory=list, max_length=20)


class ActivityFeedbackResponse(BaseModel):
    saved: bool
    message: str
