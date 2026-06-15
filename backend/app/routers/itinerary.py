from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_rag_service
from app.schemas import ActivityFeedbackRequest, ActivityFeedbackResponse, RefinementRequest, TripRequest, TripResponse
from app.services.rag import FeedbackPersistenceError, GenerationError, TravelRAGService, UnsupportedDestinationError

router = APIRouter(prefix="/api", tags=["itinerary"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/itinerary", response_model=TripResponse)
def generate_itinerary(
    trip: TripRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> TripResponse:
    try:
        return rag_service.plan_trip(trip)
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


@router.post("/itinerary/refine", response_model=TripResponse)
def refine_itinerary(
    request: RefinementRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> TripResponse:
    try:
        return rag_service.refine_trip(request)
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


@router.post("/feedback", response_model=ActivityFeedbackResponse)
def record_activity_feedback(
    feedback: ActivityFeedbackRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> ActivityFeedbackResponse:
    try:
        result = rag_service.record_activity_feedback(feedback)
    except FeedbackPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save feedback: {exc}",
        ) from exc
    return ActivityFeedbackResponse(saved=True, message=result["message"])
