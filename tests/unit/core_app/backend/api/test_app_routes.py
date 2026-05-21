from unittest.mock import MagicMock, patch


def test_health_returns_200(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"


def test_version_route(monkeypatch, app_client):
    monkeypatch.setenv("APP_IMAGE_TAG", "fru_dev_test")
    resp = app_client.get("/version")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "version" in data
    assert isinstance(data["version"], list)


def test_query_rejects_empty_body(app_client):
    resp = app_client.post("/query", json={})
    assert resp.status_code == 400


def test_query_stream_missing_query(app_client):
    resp = app_client.get("/query/stream")
    assert resp.status_code == 400


def test_query_with_mock_agent(app_client):
    from backend.api import app as app_module

    fake_agent = MagicMock()
    fake_agent.process_query.return_value = {"answer": "ok", "sources": []}
    app_module.query_agent = fake_agent
    app_module.USE_AGENT_QUERY = True
    try:
        resp = app_client.post("/query", json={"query": "how many sales?"})
        assert resp.status_code == 200
        assert resp.get_json().get("answer") == "ok"
    finally:
        app_module.query_agent = None
        app_module.USE_AGENT_QUERY = False
