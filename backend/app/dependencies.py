from functools import lru_cache

from app.config import get_settings
from app.services.rag import TravelRAGService


@lru_cache
def get_rag_service() -> TravelRAGService:
    return TravelRAGService(get_settings())
