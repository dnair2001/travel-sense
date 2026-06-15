from unittest.mock import patch

from app.dependencies import get_rag_service
from app.services.rag import TravelRAGService


def test_get_rag_service_returns_travel_rag_service():
    get_rag_service.cache_clear()
    try:
        service = get_rag_service()
        assert isinstance(service, TravelRAGService)
    finally:
        get_rag_service.cache_clear()


def test_get_rag_service_is_cached():
    get_rag_service.cache_clear()
    try:
        first = get_rag_service()
        second = get_rag_service()
        assert first is second
    finally:
        get_rag_service.cache_clear()
