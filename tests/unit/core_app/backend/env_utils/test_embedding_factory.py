from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.embedding_factory import create_embedding_client
from backend.env_utils.cloud_shared.embedding_profiles import get_profiles


@pytest.fixture(autouse=True)
def _clear_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def test_create_openai_embedding_client(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(index=0, embedding=[0.1] * 1536)]
    )
    client = create_embedding_client(openai_client=mock_client)
    vecs = client.embed_texts(["hello"])
    assert len(vecs[0]) == 1536
    assert client.profile_name == "openai_1536"


def test_create_modelark_client_dispatch(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep-test")
    with patch(
        "backend.env_utils.byteplus.embeddings.ModelArkEmbeddingClient.embed_texts",
        return_value=[[0.0] * 2048],
    ):
        client = create_embedding_client()
        assert client.dimension == 2048
        assert client.embed_texts(["x"])[0][0] == 0.0
