"""Unit tests for embedding_deploy_env (compose + kube deploy wiring)."""
from __future__ import annotations

import pytest

from tools.cloud_shared.embedding_deploy_env import (
    api_deployment_embedding_subs,
    embedding_profile_from_env,
    expand_model_defaults_for_deploy,
    modelark_secret_entries,
)


def test_embedding_profile_from_env_default(monkeypatch):
    monkeypatch.delenv("EMBEDDING_ACTIVE_PROFILE", raising=False)
    assert embedding_profile_from_env() == "openai_1536"


def test_embedding_profile_from_env_skylark(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    assert embedding_profile_from_env() == "skylark_2048"


def test_modelark_secret_entries_omits_empty(monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    assert modelark_secret_entries() == {}


def test_modelark_secret_entries_includes_key(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    assert modelark_secret_entries() == {"ARK_API_KEY": "ark-test"}


def test_expand_model_defaults_prefers_default_embedding(monkeypatch):
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROFILE", "skylark_2048")
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "seed_lite")
    monkeypatch.setenv("ALLOW_PER_REQUEST_MODEL_OVERRIDE", "false")
    subs = expand_model_defaults_for_deploy()
    assert subs["DEFAULT_EMBEDDING_PROFILE"] == "skylark_2048"
    assert subs["EMBEDDING_ACTIVE_PROFILE"] == "skylark_2048"
    assert subs["DEFAULT_CHAT_CHOICE"] == "seed_lite"
    assert subs["ALLOW_PER_REQUEST_MODEL_OVERRIDE"] == "false"


def test_api_deployment_embedding_subs_includes_model_defaults(monkeypatch):
    monkeypatch.delenv("EMBEDDING_ACTIVE_PROFILE", raising=False)
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROFILE", "openai_1536")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_API_KEY", "ck-test")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "claude_sonnet")
    subs = api_deployment_embedding_subs()
    assert subs["DEFAULT_CHAT_CHOICE"] == "claude_sonnet"
    assert "ALLOW_PER_REQUEST_MODEL_OVERRIDE" in subs
    assert "DEFAULT_EMBEDDING_PROFILE" in subs


def test_api_deployment_embedding_subs_skylark(monkeypatch):
    monkeypatch.delenv("LLM_INFERENCE_PROVIDER", raising=False)
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "claude_haiku")
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep-embed")
    monkeypatch.setenv("ARK_CHAT_MODEL_ID", "ep-chat")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example/api/v3")
    subs = api_deployment_embedding_subs()
    assert subs["EMBEDDING_ACTIVE_PROFILE"] == "skylark_2048"
    assert subs["DEFAULT_CHAT_CHOICE"] != "claude_haiku"
    assert subs["DEFAULT_CHAT_CHOICE"] in (
        "seed_lite",
        "deepseek_flash",
        "deepseek_pro",
        "seed_pro",
    )
    assert subs["LLM_INFERENCE_PROVIDER"] == "claude"
    assert subs["ARK_EMBEDDING_MODEL_ID"] == "ep-embed"
    assert subs["ARK_CHAT_MODEL_ID"] == "ep-chat"
    assert subs["ARK_BASE_URL"] == "https://ark.example/api/v3"


def test_api_deployment_embedding_subs_modelark_chat(monkeypatch):
    monkeypatch.setenv("LLM_INFERENCE_PROVIDER", "modelark")
    subs = api_deployment_embedding_subs()
    assert subs["LLM_INFERENCE_PROVIDER"] == "modelark"
