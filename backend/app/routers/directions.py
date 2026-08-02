from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.dependencies import get_routing_service
from app.schemas import DirectionsRequest, RouteResponse
from app.services.routing import RoutingError, RoutingService

router = APIRouter(prefix="/api/directions", tags=["directions"])


@router.post("", response_model=RouteResponse)
def get_directions(
    request: DirectionsRequest,
    routing_service: RoutingService = Depends(get_routing_service),
    user_id: str = Depends(get_current_user),
) -> RouteResponse:
    try:
        result = routing_service.get_route(request.coordinates)
    except RoutingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return RouteResponse(**result)
