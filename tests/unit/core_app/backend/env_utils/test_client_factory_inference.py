"""Unit: create_llm_client dispatches by LLM_INFERENCE_PROVIDER."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.client_factory import create_llm_client


class _FakeLLM:
    def complete(self, *a, **kw):
        return {"text": "ok", "tokens": {}}

    def stream_complete(self, *a, **kw):
        yield "ok"


def test_modelark_provider_uses_modelark_client(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "modelark")
    monkeypatch.setenv("ARK_API_KEY", "ark-key")
    monkeypatch.setenv("ARK_CHAT_MODEL_ID", "ep-chat")
    fake = MagicMock()
    with patch(
        "backend.env_utils.byteplus.modelark_client.ModelArkClient",
        return_value=fake,
    ) as ctor:
        client = create_llm_client()
    ctor.assert_called_once()
    assert client is fake


def test_claude_default_uses_local_when_cloud_provider_local(monkeypatch):
    monkeypatch.delenv("LLM_INFERENCE_PROVIDER", raising=False)
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    with patch(
        "backend.env_utils.local.get_llm_client",
        return_value=_FakeLLM(),
    ):
        client = create_llm_client()
    assert client.complete("s", "u")["text"] == "ok"


def test_claude_explicit_does_not_use_modelark_when_ark_set(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "claude")
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    monkeypatch.setenv("ARK_API_KEY", "ark-key")
    monkeypatch.setenv("ARK_CHAT_MODEL_ID", "ep-chat")
    with patch(
        "backend.env_utils.byteplus.modelark_client.ModelArkClient",
    ) as modelark_ctor:
        with patch(
            "backend.env_utils.local.get_llm_client",
            return_value=_FakeLLM(),
        ):
            create_llm_client()
    modelark_ctor.assert_not_called()


def test_unknown_inference_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="not allowed"):
        create_llm_client()
