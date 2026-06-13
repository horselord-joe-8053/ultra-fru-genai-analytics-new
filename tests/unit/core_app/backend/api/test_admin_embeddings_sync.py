import os
from unittest.mock import MagicMock, patch

import pytest

from backend.api import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PGHOST", "localhost")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_admin_sync_disabled_without_key(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    resp = client.post("/admin/embeddings/sync", json={"scope": "all"})
    assert resp.status_code == 503


def test_admin_sync_forbidden_wrong_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    resp = client.post(
        "/admin/embeddings/sync",
        json={"scope": "all"},
        headers={"X-Admin-Api-Key": "wrong"},
    )
    assert resp.status_code == 403


def test_admin_sync_all_success(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    mock_result = MagicMock()
    mock_result.to_dict.return_value = {"embedded": 5, "failed": 0}

    with patch("backend.api.app.get_db_conn", return_value=MagicMock()):
        with patch("backend.api.app.return_db_conn"):
            with patch(
                "backend.services.embedding_sync.sync_all_embeddings",
                return_value=mock_result,
            ):
                resp = client.post(
                    "/admin/embeddings/sync",
                    json={"scope": "all"},
                    headers={"X-Admin-Api-Key": "secret"},
                )
    assert resp.status_code == 200
    assert resp.get_json()["embedded"] == 5
