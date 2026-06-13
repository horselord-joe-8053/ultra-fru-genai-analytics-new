"""Unit tests for embedding_sync_core (shared orchestration)."""
from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import get_profiles
from backend.services import embedding_sync_core as core


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_core_profile_loop_calls_embed_per_available_profile(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("ARK_API_KEY", "a")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "m")

    writes: list[tuple[str, str]] = []

    def write_vector(prof, rid, vector):
        writes.append((prof.pgvector_column, rid))

    row_map = {"F1": ("feedback text", {"embedding_openai_1536": None, "embedding_skylark_2048": None})}

    mock_openai = MagicMock()
    mock_openai.embed_texts.return_value = [[0.1] * 1536]
    mock_skylark = MagicMock()
    mock_skylark.embed_texts.return_value = [[0.2] * 2048]

    def factory(profile=None, openai_client=None):
        if profile.name == "openai_1536":
            return mock_openai
        return mock_skylark

    with patch("backend.services.embedding_sync_core.create_embedding_client", side_effect=factory):
        result = core.sync_embeddings_core(
            ["F1"], row_map, force=True, write_vector=write_vector
        )

    assert result.embedded == 2
    cols = {w[0] for w in writes}
    assert "embedding_openai_1536" in cols
    assert "embedding_skylark_2048" in cols


def test_core_never_reads_active_profile_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")

    with patch("backend.env_utils.cloud_shared.embedding_profiles.get_active_profile") as mock_active:
        core.sync_embeddings_core(
            ["F1"],
            {"F1": ("x", {})},
            force=True,
            write_vector=lambda *a: None,
        )
    mock_active.assert_not_called()


def test_core_skips_column_when_not_force_and_nonnull(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    writes = []

    with patch("backend.services.embedding_sync_core.create_embedding_client") as mock_factory:
        result = core.sync_embeddings_core(
            ["F1"],
            {"F1": ("x", {"embedding_openai_1536": [0.0] * 1536})},
            force=False,
            write_vector=lambda *a: writes.append(a),
        )
    mock_factory.assert_not_called()
    assert result.skipped == 1
    assert not writes


def test_core_force_reembeds_nonempty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    writes = []
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1] * 1536]

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        core.sync_embeddings_core(
            ["F1"],
            {"F1": ("x", {"embedding_openai_1536": [0.0] * 1536})},
            force=True,
            write_vector=lambda prof, rid, vec: writes.append(prof.pgvector_column),
        )
    assert writes == ["embedding_openai_1536"]


def test_core_partial_profile_failure_sync_result(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    mock_client = MagicMock()
    mock_client.embed_texts.side_effect = RuntimeError("API down")

    with patch("backend.services.embedding_sync_core.create_embedding_client", return_value=mock_client):
        result = core.sync_embeddings_core(
            ["F1"],
            {"F1": ("x", {})},
            force=True,
            write_vector=lambda *a: None,
        )
    assert result.failed == 1
    assert result.errors


def test_psycopg2_and_rds_adapters_both_import_core():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[5]
    pg = (repo / "core_app/backend/services/embedding_sync.py").read_text()
    rds = (repo / "core_app/backend/services/embedding_sync_rds.py").read_text()
    assert "embedding_sync_core" in pg
    assert "sync_embeddings_core" in pg
    assert "embedding_sync_core" in rds
    assert "sync_embeddings_core" in rds
