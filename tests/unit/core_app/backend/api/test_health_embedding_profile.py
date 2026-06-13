"""Unit: /health reports modelark_embeddings configured when ARK_* env is set."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_health_modelark_configured_when_profile_and_ark_set(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "skylark_2048")
    monkeypatch.setenv("ARK_API_KEY", "ark-test")
    monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep-embed")

    from backend.env_utils.cloud_shared.embedding_profiles import get_profiles

    get_profiles.cache_clear()

    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = lambda s: cursor
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor

    from backend.api import app as app_module

    monkeypatch.setattr(app_module, "get_db_conn", lambda: conn)
    monkeypatch.setattr(app_module, "return_db_conn", lambda c: None)

    client = app_module.app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("embedding_profile") == "skylark_2048"
    assert data.get("modelark_embeddings") == "configured"

    get_profiles.cache_clear()
