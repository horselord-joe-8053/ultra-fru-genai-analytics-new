import pytest

from tools.cloud_shared.env import EnvVarNotFound, validate_active_embedding_profile_env
from backend.env_utils.cloud_shared.embedding_profiles import get_profiles


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_validate_modelark_profile_requires_ark_vars(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    with pytest.raises(EnvVarNotFound):
        validate_active_embedding_profile_env()


def test_validate_openai_profile_requires_api_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EnvVarNotFound):
        validate_active_embedding_profile_env()
