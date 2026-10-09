"""Unit: LLM_INFERENCE_PROVIDER resolution."""
from __future__ import annotations

import pytest

from backend.env_utils.cloud_shared.llm_inference_config import (
    DEFAULT_LLM_INFERENCE_PROVIDER,
    chat_model_env_for_provider,
    get_llm_inference_provider,
)


def test_unset_defaults_to_claude(monkeypatch):
    monkeypatch.delenv("LLM_INFERENCE_PROVIDER", raising=False)
    assert get_llm_inference_provider() == DEFAULT_LLM_INFERENCE_PROVIDER


def test_empty_string_defaults_to_claude(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "   ")
    assert get_llm_inference_provider() == "claude"


@pytest.mark.parametrize("raw,expected", [("modelark", "modelark"), ("Claude", "claude"), ("MODELARK", "modelark")])
def test_allowed_values_normalized(monkeypatch, raw, expected):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", raw)
    assert get_llm_inference_provider() == expected


def test_unknown_provider_raises_with_allowlist(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "openai")
    with pytest.raises(ValueError, match="not allowed"):
        get_llm_inference_provider()


def test_unknown_provider_message_lists_allowlist(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "bedrock")
    with pytest.raises(ValueError) as exc:
        get_llm_inference_provider()
    msg = str(exc.value)
    assert "claude" in msg
    assert "modelark" in msg


def test_chat_model_env_modelark():
    env = chat_model_env_for_provider("modelark")
    assert "ARK_CHAT_MODEL_ID" in env
    assert "ARK_API_KEY" in env


def test_chat_model_env_claude_local(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    env = chat_model_env_for_provider("claude")
    assert env["CLAUDE_MODEL"] == "Claude model id"
