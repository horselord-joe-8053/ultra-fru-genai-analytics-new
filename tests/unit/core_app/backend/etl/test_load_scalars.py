from pathlib import Path

import os
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[5]


def test_scalar_loader_no_profile_flag():
    path = _REPO / "core_app/backend/etl/load_openai_embeddings_to_pgvector.py"
    source = path.read_text()
    assert "--profile" not in source
    assert "EMBEDDING_ACTIVE_PROFILE" not in source
    assert "sync_all_embeddings" in source or "sync-embeddings" in source


def test_load_embeddings_calls_sync(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.side_effect = [(0,), (0,)]

    with patch("backend.services.embedding_sync.copy_raw_to_embeddings_scalars", return_value=10):
        with patch(
            "backend.services.embedding_sync.sync_all_embeddings",
            return_value=MagicMock(embedded=20, skipped=0, failed=0, to_dict=dict),
        ) as mock_sync:
            from tools.gcp.scope_shared.deploy.db_setup.load import load_embeddings

            count = load_embeddings(conn, csv_path=None, force=False)
    mock_sync.assert_called_once()
