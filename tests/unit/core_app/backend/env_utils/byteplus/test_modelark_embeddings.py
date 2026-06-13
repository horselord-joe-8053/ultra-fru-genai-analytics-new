import json
from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.byteplus.embeddings import ModelArkEmbeddingClient
from backend.env_utils.cloud_shared.embedding_profiles import EmbeddingProfile, get_profiles


@pytest.fixture
def skylark_profile():
    get_profiles.cache_clear()
    yield get_profiles()["skylark_2048"]
    get_profiles.cache_clear()


def test_modelark_embed_texts_returns_2048_vectors(monkeypatch, skylark_profile):
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "skylark-embedding-vision-251215")
    calls = []

    def fake_urlopen(req, timeout=120):
        assert req.get_header("Authorization") == "Bearer test-key"
        assert req.full_url.endswith("/embeddings/multimodal")
        body = json.loads(req.data.decode())
        calls.append(body)
        resp = MagicMock()
        resp.read.return_value = json.dumps(
            {"data": {"embedding": [0.1] * 2048}}
        ).encode()
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        client = ModelArkEmbeddingClient(skylark_profile)
        vectors = client.embed_texts(["a", "b"])
    assert len(calls) == 2
    assert calls[0]["input"] == [{"type": "text", "text": "a"}]
    assert len(vectors) == 2
    assert len(vectors[0]) == 2048
    assert client.profile_name == "skylark_2048"


def test_modelark_embed_dimension_mismatch_raises(monkeypatch, skylark_profile):
    monkeypatch.setenv("ARK_API_KEY", "k")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "skylark-embedding-vision-251215")
    payload = {"data": {"embedding": [0.0] * 100}}

    def fake_urlopen(req, timeout=120):
        resp = MagicMock()
        resp.read.return_value = json.dumps(payload).encode()
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        client = ModelArkEmbeddingClient(skylark_profile)
        with pytest.raises(ValueError, match="dimension"):
            client.embed_texts(["x"])
