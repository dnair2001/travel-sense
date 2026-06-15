from unittest.mock import MagicMock, patch

from app.ingest import main


def test_main_calls_rebuild_and_prints_summary(capsys):
    fake_service = MagicMock()
    fake_service.rebuild_vectorstore.return_value = {
        "documents": 10,
        "chunks": 25,
        "cities": 3,
        "personal_documents": 4,
    }

    with patch("app.ingest.get_rag_service", return_value=fake_service):
        main()

    fake_service.rebuild_vectorstore.assert_called_once()
    captured = capsys.readouterr()
    assert "10 documents" in captured.out
    assert "25 chunks" in captured.out
    assert "3 cities" in captured.out
