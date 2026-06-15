from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_calls_ensure_index():
    mock_service = MagicMock()

    with patch("app.main.get_rag_service", return_value=mock_service):
        with TestClient(app):
            pass

    mock_service.ensure_index.assert_called_once()
