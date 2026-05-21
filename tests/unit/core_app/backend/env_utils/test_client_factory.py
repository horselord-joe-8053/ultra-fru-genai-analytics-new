from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.client_factory import create_llm_client


class _FakeLLM:
    def complete(self, *a, **kw):
        return {"text": "ok", "tokens": {}}

    def stream_complete(self, *a, **kw):
        yield "ok"


def test_create_llm_client_explicit_local(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    with patch(
        "backend.env_utils.local.get_llm_client",
        return_value=_FakeLLM(),
    ):
        client = create_llm_client()
    assert client.complete("s", "u")["text"] == "ok"


def test_create_llm_client_missing_raises(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "aws")
    with patch("backend.env_utils.aws.get_llm_client", return_value=None):
        with pytest.raises(ValueError, match="No LLM client"):
            create_llm_client()
