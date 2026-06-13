import os
from unittest.mock import patch

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import get_active_pgvector_column, get_profiles


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_default_profile_column_openai(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    assert get_active_pgvector_column() == "embedding_openai_1536"


def test_profile_env_skylark_column(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    assert get_active_pgvector_column() == "embedding_skylark_2048"


def test_load_cli_profile_overrides_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    with patch("sys.argv", ["load_openai_embeddings_to_pgvector.py", "--profile", "skylark_2048"]):
        with patch(
            "core_app.backend.etl.load_openai_embeddings_to_pgvector.pd.read_csv",
            side_effect=RuntimeError("stop-after-profile"),
        ):
            from core_app.backend.etl.load_openai_embeddings_to_pgvector import main

            with pytest.raises(RuntimeError, match="stop-after-profile"):
                main()
    assert os.environ["EMBEDDING_ACTIVE_PROFILE"] == "skylark_2048"
    assert get_active_pgvector_column() == "embedding_skylark_2048"
