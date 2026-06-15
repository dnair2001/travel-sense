from functools import wraps
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_rag_service
from app.schemas import ActivityFeedbackRequest, ActivityFeedbackResponse, RefinementRequest, TripRequest, TripResponse
from app.services.rag import GenerationError, TravelRAGService, UnsupportedDestinationError

router = APIRouter(prefix="/api", tags=["itinerary"])

T = TypeVar("T")


def handle_rag_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Wrap a route handler so RAG service errors become HTTP errors."""

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> T:
        try:
            return func(*args, **kwargs)
        except UnsupportedDestinationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported destination '{exc.destination}'. Available destinations: Paris, Tokyo, NYC.",
            ) from exc
        except GenerationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The itinerary model returned an invalid response. Please try again.",
            ) from exc

    return wrapper  # type: ignore[return-value]


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/itinerary", response_model=TripResponse)
@handle_rag_errors
def generate_itinerary(
    trip: TripRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> TripResponse:
    return rag_service.plan_trip(trip)


@router.post("/itinerary/refine", response_model=TripResponse)
@handle_rag_errors
def refine_itinerary(
    request: RefinementRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> TripResponse:
    return rag_service.refine_trip(request)


@router.post("/feedback", response_model=ActivityFeedbackResponse)
def record_activity_feedback(
    feedback: ActivityFeedbackRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> ActivityFeedbackResponse:
    result = rag_service.record_activity_feedback(feedback)
    return ActivityFeedbackResponse(saved=True, message=result["message"])
