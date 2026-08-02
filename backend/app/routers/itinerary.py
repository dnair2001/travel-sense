from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.dependencies import get_rag_service
from app.schemas import ActivityFeedbackRequest, ActivityFeedbackResponse, RefinementRequest, TripRequest, TripResponse
from app.services.rag import GenerationError, TravelRAGService, UnsupportedDestinationError

router = APIRouter(prefix="/api", tags=["itinerary"])


def _unsupported_destination_error(exc: UnsupportedDestinationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"No sources found for '{exc.destination}'. "
            "Add a blog or YouTube link for this destination first."
        ),
    )


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/itinerary", response_model=TripResponse)
def generate_itinerary(
    trip: TripRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
    user_id: str = Depends(get_current_user),
) -> TripResponse:
    try:
        return rag_service.plan_trip(trip, user_id)
    except UnsupportedDestinationError as exc:
        raise _unsupported_destination_error(exc) from exc
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The itinerary model returned an invalid response. Please try again.",
        ) from exc


@router.post("/itinerary/refine", response_model=TripResponse)
def refine_itinerary(
    request: RefinementRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
    user_id: str = Depends(get_current_user),
) -> TripResponse:
    try:
        return rag_service.refine_trip(request, user_id)
    except UnsupportedDestinationError as exc:
        raise _unsupported_destination_error(exc) from exc
    except GenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The itinerary model returned an invalid response. Please try again.",
        ) from exc


@router.post("/feedback", response_model=ActivityFeedbackResponse)
def record_activity_feedback(
    feedback: ActivityFeedbackRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
    user_id: str = Depends(get_current_user),
) -> ActivityFeedbackResponse:
    result = rag_service.record_activity_feedback(feedback, user_id)
    return ActivityFeedbackResponse(saved=True, message=result["message"])
