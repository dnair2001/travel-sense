from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.dependencies import get_ingestion_service
from app.schemas import (
    SourceDeleteRequest,
    SourceDeleteResponse,
    SourceIngestRequest,
    SourceIngestResponse,
    SourceListResponse,
)
from app.services.ingestion import IngestionError, SourceIngestionService

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("", response_model=SourceIngestResponse)
def ingest_source(
    request: SourceIngestRequest,
    ingestion_service: SourceIngestionService = Depends(get_ingestion_service),
    user_id: str = Depends(get_current_user),
) -> SourceIngestResponse:
    try:
        result = ingestion_service.ingest(user_id, request.destination, request.url)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SourceIngestResponse.model_validate(result)


@router.get("", response_model=SourceListResponse)
def list_sources(
    destination: Optional[str] = None,
    ingestion_service: SourceIngestionService = Depends(get_ingestion_service),
    user_id: str = Depends(get_current_user),
) -> SourceListResponse:
    sources = ingestion_service.list_sources(user_id, destination)
    return SourceListResponse(sources=sources)


@router.delete("", response_model=SourceDeleteResponse)
def delete_source(
    request: SourceDeleteRequest,
    ingestion_service: SourceIngestionService = Depends(get_ingestion_service),
    user_id: str = Depends(get_current_user),
) -> SourceDeleteResponse:
    ingestion_service.delete_source(user_id, request.url)
    return SourceDeleteResponse(deleted=True)
