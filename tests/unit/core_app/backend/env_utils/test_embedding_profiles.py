import os
from pathlib import Path

import pytest

from backend.env_utils.cloud_shared.embedding_profiles import (
    get_active_pgvector_column,
    get_active_profile,
    get_profiles,
    load_profiles,
    validate_profile,
    EmbeddingProfile,
)


@pytest.fixture(autouse=True)
def _clear_profile_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_load_profiles_validates_column_names():
    from backend.env_utils.cloud_shared.embedding_profiles import default_profiles_path

    profiles = load_profiles(default_profiles_path())
    assert "openai_1536" in profiles
    assert profiles["openai_1536"].pgvector_column == "embedding_openai_1536"
    assert profiles["skylark_2048"].dimension == 2048


def test_validate_profile_rejects_bad_column():
    bad = EmbeddingProfile(
        name="bad",
        provider="openai",
        model_slug="openai",
        model_env="OPENAI_EMBED_MODEL",
        dimension=1536,
        pgvector_column="embedding_wrong_name",
    )
    with pytest.raises(ValueError, match="pgvector_column must be"):
        validate_profile(bad)


def test_get_active_profile_default(monkeypatch):
    monkeypatch.delenv("EMBEDDING_ACTIVE_PROFILE", raising=False)
    p = get_active_profile()
    assert p.name == "openai_1536"


def test_get_active_profile_unknown(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "no_such_profile")
    with pytest.raises(ValueError, match="Unknown EMBEDDING_ACTIVE_PROFILE"):
        get_active_profile()


def test_get_active_pgvector_column(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    assert get_active_pgvector_column() == "embedding_skylark_2048"
