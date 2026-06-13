from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import get_profiles


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_sync_row_embeddings_delegates(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    from backend.api.app import _sync_row_embeddings

    conn = MagicMock()
    with patch("backend.services.embedding_sync.sync_embeddings_for_ids") as mock_sync:
        mock_sync.return_value = MagicMock(
            to_dict=lambda: {"embedded": 2, "warnings": [], "errors": []}
        )
        out = _sync_row_embeddings(conn, "F1")
    mock_sync.assert_called_once_with(conn, ["F1"], force=True)
    assert out["embedded"] == 2


def test_crud_embed_ignores_active_profile(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    from backend.api.app import _sync_row_embeddings

    conn = MagicMock()
    with patch("backend.services.embedding_sync.sync_embeddings_for_ids") as mock_sync:
        mock_sync.return_value = MagicMock(to_dict=lambda: {"embedded": 2})
        _sync_row_embeddings(conn, "X")
    assert mock_sync.call_args.kwargs.get("force") is True
    assert "skylark" not in str(mock_sync.call_args)


def test_upsert_scalar_row_no_embed_columns():
    from backend.services.embedding_sync import SCALAR_UPSERT_SQL

    assert "embedding_" not in SCALAR_UPSERT_SQL
