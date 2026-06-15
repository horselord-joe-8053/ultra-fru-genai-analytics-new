"""Unit tests for model stack catalog, resolver, and validation."""
import pytest

from backend.env_utils.cloud_shared.model_profiles import (
    chat_choices_for_embedding,
    clear_model_profiles_cache,
    is_valid_stack_pair,
    resolve_chat_model_id,
    resolve_request_model_context,
    validate_model_catalog_defaults,
)


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    clear_model_profiles_cache()
    yield
    clear_model_profiles_cache()


@pytest.fixture
def _local_claude_creds(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROFILE", "openai_1536")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "claude_haiku")


@pytest.fixture
def _all_creds(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "local")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep-embed-test")


def test_resolve_chat_model_id_local_claude(_local_claude_creds, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-4-5")
    assert resolve_chat_model_id("claude_haiku") == "claude-haiku-4-5"


def test_resolve_chat_model_id_aws_bedrock_haiku(monkeypatch):
    monkeypatch.setenv("CLOUD_PROVIDER", "aws")
    monkeypatch.setenv("AWS_BEDROCK_INFERENCE_PROFILE_ID", "global-profile")
    mid = resolve_chat_model_id("claude_haiku")
    assert mid == "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_resolve_chat_model_id_modelark_yaml_id(_all_creds):
    assert resolve_chat_model_id("deepseek_flash") == "deepseek-v4-flash-260425"
    assert resolve_chat_model_id("seed_lite") == "seed-2-0-lite-260228"


def test_valid_openai_claude_stack(_local_claude_creds):
    ctx = resolve_request_model_context("openai_1536", "claude_haiku")
    assert ctx.embedding_profile == "openai_1536"
    assert ctx.chat_choice == "claude_haiku"
    assert ctx.chat_model_id
    assert ctx.embedding_display
    assert ctx.chat_display == "claude-haiku-4-5"


def test_invalid_cross_stack_rejected(_all_creds):
    with pytest.raises(ValueError, match="Invalid model stack"):
        resolve_request_model_context("skylark_2048", "claude_haiku")


def test_chat_choices_for_embedding_openai(_local_claude_creds):
    choices = chat_choices_for_embedding("openai_1536")
    assert "claude_haiku" in choices
    assert "claude_sonnet" in choices
    assert "seed_lite" not in choices


def test_chat_choices_for_embedding_skylark(_all_creds):
    choices = chat_choices_for_embedding("skylark_2048")
    assert "seed_lite" in choices
    assert "deepseek_flash" in choices
    assert "claude_haiku" not in choices


def test_is_valid_stack_pair(_local_claude_creds):
    assert is_valid_stack_pair("openai_1536", "claude_haiku")
    assert not is_valid_stack_pair("openai_1536", "seed_lite")


def test_override_disabled_rejects_non_default(_local_claude_creds, monkeypatch):
    monkeypatch.setenv("ALLOW_PER_REQUEST_MODEL_OVERRIDE", "false")
    with pytest.raises(PermissionError):
        resolve_request_model_context("openai_1536", "claude_sonnet")


def test_validate_defaults_enabled_stack(_local_claude_creds):
    assert validate_model_catalog_defaults() == []


def test_build_model_catalog_includes_stacks(_local_claude_creds):
    from backend.env_utils.cloud_shared.model_profiles import build_model_catalog

    catalog = build_model_catalog()
    assert "stacks" in catalog
    assert catalog["cloud_provider"] == "local"
    assert "allow_override" in catalog
    assert any(s["enabled"] for s in catalog["stacks"])


def test_request_context_includes_chat_model_id(_local_claude_creds):
    ctx = resolve_request_model_context("openai_1536", "claude_sonnet")
    assert ctx.chat_model_id == "claude-sonnet-4-20250514"
