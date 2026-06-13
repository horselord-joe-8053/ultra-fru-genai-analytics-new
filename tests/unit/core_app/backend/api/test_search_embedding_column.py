from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import get_profiles


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_upsert_embeddings_targets_active_column(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    from backend.api.app import _upsert_embeddings_for_rows

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    row = {
        "ID": "1",
        "CUSTOMER_FEEDBACK": "great fridge",
        "BRAND": "Fru",
        "FRIDGE_MODEL": "X",
        "PRICE": 100,
        "SALES_DATE": "2024-01-01",
        "STORE_NAME": "Store",
    }
    with patch(
        "backend.env_utils.cloud_shared.embedding_factory.create_embedding_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.embed_texts.return_value = [[0.1] * 1536]
        mock_factory.return_value = mock_client
        with patch("backend.api.app.get_openai_client", return_value=MagicMock()):
            _upsert_embeddings_for_rows(conn, [row])

    sql = cursor.execute.call_args[0][0]
    assert "embedding_openai_1536" in sql
    assert "EXCLUDED.embedding_openai_1536" in sql
