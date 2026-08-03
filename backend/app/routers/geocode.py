from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.dependencies import get_geocoding_service
from app.schemas import GeocodeResponse
from app.services.geocoding import GeocodingService

router = APIRouter(prefix="/api/geocode", tags=["geocode"])


@router.get("", response_model=GeocodeResponse)
def geocode(
    query: str = Query(..., min_length=1),
    geocoding_service: GeocodingService = Depends(get_geocoding_service),
    user_id: str = Depends(get_current_user),
) -> GeocodeResponse:
    result = geocoding_service.geocode(query)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No location found for '{query}'.")
    lat, lng, label, is_approximate = result
    return GeocodeResponse(lat=lat, lng=lng, label=label, is_approximate=is_approximate)
