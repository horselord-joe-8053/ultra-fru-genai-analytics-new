"""Unit tests for model catalog defaults and /model-catalog route."""
from unittest.mock import MagicMock, patch

import pytest

from backend.env_utils.cloud_shared.model_profiles import (
    get_default_chat_choice_name,
    get_default_embedding_profile_name,
    validate_model_catalog_defaults,
)


def test_validate_model_catalog_defaults_ok(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROFILE", "openai_1536")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "claude_haiku")
    errs = validate_model_catalog_defaults()
    assert errs == []


def test_validate_model_catalog_unknown_default(monkeypatch):
    monkeypatch.setenv("DEFAULT_EMBEDDING_PROFILE", "nonexistent_profile")
    monkeypatch.setenv("DEFAULT_CHAT_CHOICE", "claude_haiku")
    errs = validate_model_catalog_defaults()
    assert any("nonexistent_profile" in e for e in errs)


def test_model_catalog_route(app_client):
    with patch("backend.api.app.get_db_conn") as mock_conn:
        mock_conn.return_value = MagicMock()
        with patch(
            "backend.env_utils.cloud_shared.model_profiles.build_model_catalog",
            return_value={
                "cloud_provider": "local",
                "allow_override": True,
                "stacks": [
                    {
                        "embedding_profile": "openai_1536",
                        "chat_choice": "claude_haiku",
                        "enabled": True,
                        "stack_group": "openai_claude",
                    }
                ],
                "embeddings": [{"id": "openai_1536", "display": "text-embedding-3-small", "enabled": True}],
                "chat": [{"id": "claude_haiku", "display": "claude-haiku-4-5", "enabled": True}],
                "defaults": {
                    "embedding_profile": get_default_embedding_profile_name(),
                    "chat_choice": get_default_chat_choice_name(),
                },
            },
        ):
            resp = app_client.get("/model-catalog")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "embeddings" in body
    assert "chat" in body
    assert "stacks" in body
    assert "cloud_provider" in body
    assert "allow_override" in body
    assert "defaults" in body
