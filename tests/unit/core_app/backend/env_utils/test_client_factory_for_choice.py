"""Unit: create_llm_client_for_choice uses catalog inference, not global LLM_INFERENCE_PROVIDER."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.client_factory import create_llm_client_for_choice
from backend.env_utils.cloud_shared.model_profiles import clear_model_profiles_cache


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    clear_model_profiles_cache()
    yield
    clear_model_profiles_cache()


class _FakeLLM:
    def complete(self, *a, **kw):
        return {"text": "ok", "tokens": {}}

    def stream_complete(self, *a, **kw):
        yield "ok"


def test_claude_sonnet_ignores_global_modelark_provider(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "modelark")
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    with patch(
        "backend.env_utils.byteplus.modelark_client.ModelArkClient",
    ) as modelark_ctor:
        with patch(
            "backend.env_utils.local.get_llm_client",
            return_value=_FakeLLM(),
        ) as local_ctor:
            client = create_llm_client_for_choice("claude_sonnet")
    modelark_ctor.assert_not_called()
    local_ctor.assert_called_once()
    assert client.complete("s", "u")["text"] == "ok"


def test_modelark_seed_lite_ignores_global_claude_provider(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "claude")
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    fake = MagicMock()
    with patch(
        "backend.env_utils.byteplus.modelark_client.ModelArkClient",
        return_value=fake,
    ) as modelark_ctor:
        with patch(
            "backend.env_utils.local.get_llm_client",
        ) as local_ctor:
            client = create_llm_client_for_choice("seed_lite")
    modelark_ctor.assert_called_once()
    local_ctor.assert_not_called()
    assert client is fake


def test_unknown_chat_choice_raises(monkeypatch):
    with pytest.raises(ValueError, match="Unknown chat_choice"):
        create_llm_client_for_choice("not_a_profile")
