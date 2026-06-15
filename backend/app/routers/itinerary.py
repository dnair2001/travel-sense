from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies import get_rag_service
from app.schemas import ActivityFeedbackRequest, ActivityFeedbackResponse, RefinementRequest, TripRequest, TripResponse
from app.services.rag import GenerationError, TravelRAGService, UnsupportedDestinationError

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api", tags=["itinerary"])


@router.get("/health")
@limiter.limit("30/minute")
def healthcheck(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@router.post("/itinerary", response_model=TripResponse)
@limiter.limit("10/minute")
def generate_itinerary(
    request: Request,
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
@limiter.limit("10/minute")
def refine_itinerary(
    request: Request,
    body: RefinementRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> TripResponse:
    try:
        return rag_service.refine_trip(body)
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
@limiter.limit("20/minute")
def record_activity_feedback(
    request: Request,
    feedback: ActivityFeedbackRequest,
    rag_service: TravelRAGService = Depends(get_rag_service),
) -> ActivityFeedbackResponse:
    result = rag_service.record_activity_feedback(feedback)
    return ActivityFeedbackResponse(saved=True, message=result["message"])
