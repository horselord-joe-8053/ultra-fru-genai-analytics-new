"""Unit tests for embedding_sync service."""
from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, get_profiles
from backend.services import embedding_sync as es


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


@pytest.fixture
def openai_profile():
    return get_profiles()["openai_1536"]


@pytest.fixture
def skylark_profile():
    return get_profiles()["skylark_2048"]


def test_available_profiles_filters_by_credentials(monkeypatch, openai_profile, skylark_profile):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    names = [p.name for p in es.available_profiles()]
    assert names == ["openai_1536"]

    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")
    names = [p.name for p in es.available_profiles()]
    assert "openai_1536" in names
    assert "skylark_2048" in names


def test_sync_for_ids_updates_both_columns(monkeypatch, openai_profile, skylark_profile):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    cursor.fetchall.return_value = [
        ("F1", "great fridge", None, None),
    ]

    mock_openai = MagicMock()
    mock_openai.embed_texts.return_value = [[0.1] * 1536]
    mock_skylark = MagicMock()
    mock_skylark.embed_texts.return_value = [[0.2] * 2048]

    def factory(profile=None, openai_client=None):
        if profile.name == "openai_1536":
            return mock_openai
        return mock_skylark

    with patch("backend.services.embedding_sync_core.create_embedding_client", side_effect=factory):
        result = es.sync_embeddings_for_ids(conn, ["F1"], force=True)

    assert result.embedded == 2
    assert result.failed == 0
    assert cursor.execute.call_count >= 2
    update_sqls = [c[0][0] for c in cursor.execute.call_args_list if "UPDATE" in c[0][0]]
    assert any("embedding_openai_1536" in s for s in update_sqls)
    assert any("embedding_skylark_2048" in s for s in update_sqls)


def test_sync_for_ids_skips_populated_when_not_force(monkeypatch, openai_profile):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [("F1", "text", [0.0] * 1536, None)]

    with patch("backend.services.embedding_sync_core.create_embedding_client") as mock_factory:
        result = es.sync_embeddings_for_ids(conn, ["F1"], force=False)
    mock_factory.assert_not_called()
    assert result.skipped == 1


def test_sync_all_missing_only_selects_gaps(monkeypatch, openai_profile, skylark_profile):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.side_effect = [
        [("F900",)],
        [("F900", "feedback", [0.1] * 1536, None)],
    ]

    with patch(
        "backend.services.embedding_sync.sync_embeddings_for_ids",
        return_value=es.SyncResult(embedded=2),
    ) as mock_sync:
        result = es.sync_all_embeddings(conn, missing_only=True)

    mock_sync.assert_called_once()
    assert mock_sync.call_args[0][1] == ["F900"]
    assert result.embedded == 2


def test_sync_result_partial_failure(monkeypatch, openai_profile):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [("F1", "x", None, None)]

    mock_client = MagicMock()
    mock_client.embed_texts.side_effect = RuntimeError("API down")

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        result = es.sync_embeddings_for_ids(conn, ["F1"], force=True)

    assert result.failed == 1
    assert result.errors
