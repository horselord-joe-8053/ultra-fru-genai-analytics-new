from unittest.mock import MagicMock, patch

import pytest

from backend.agents.tools.semantic_search_tool import SemanticSearchTool
from backend.env_utils.cloud_shared.embedding_profiles import get_profiles


@pytest.fixture(autouse=True)
def _clear_profiles_cache():
    get_profiles.cache_clear()
    yield
    get_profiles.cache_clear()


def _mock_db_pool(rows=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = lambda s: cursor
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = rows or []
    conn.cursor.return_value = cursor
    pool = MagicMock()
    pool.getconn.return_value = conn
    return pool, cursor


@pytest.mark.parametrize(
    "profile_name,column",
    [
        ("openai_1536", "embedding_openai_1536"),
        ("skylark_2048", "embedding_skylark_2048"),
    ],
)
def test_semantic_search_sql_uses_active_profile_column(monkeypatch, profile_name, column):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", profile_name)
    if profile_name == "skylark_2048":
        monkeypatch.setenv("ARK_API_KEY", "k")
        monkeypatch.setenv("ARK_EMBEDDING_MODEL_ID", "ep")

    pool, cursor = _mock_db_pool()
    tool = SemanticSearchTool(pool, openai_client=MagicMock())

    dim = 1536 if profile_name == "openai_1536" else 2048
    fake_vec = [0.0] * dim
    with patch(
        "backend.agents.tools.semantic_search_tool.create_embedding_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.embed_texts.return_value = [fake_vec]
        mock_factory.return_value = mock_client
        result = tool.execute(query_text="noisy fridge feedback", limit=5)

    assert result["success"] is True
    executed_sql = cursor.execute.call_args[0][0]
    assert column in executed_sql
    assert "ORDER BY" in executed_sql
    assert "AS distance" in executed_sql


def test_semantic_search_default_limit_is_25(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    monkeypatch.delenv("SEMANTIC_SEARCH_DEFAULT_LIMIT", raising=False)
    pool, cursor = _mock_db_pool()
    tool = SemanticSearchTool(pool, openai_client=MagicMock())
    fake_vec = [0.0] * 1536
    with patch(
        "backend.agents.tools.semantic_search_tool.create_embedding_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.embed_texts.return_value = [fake_vec]
        mock_factory.return_value = mock_client
        tool.execute(query_text="water leakage")
    params = cursor.execute.call_args[0][1]
    assert params[-1] == 25


def test_semantic_search_top_preview_truncates_feedback(monkeypatch):
    monkeypatch.setenv("EMBEDDING_ACTIVE_PROFILE", "openai_1536")
    long_feedback = "water " * 40
    rows = [
        {
            "id": "F032",
            "store_name": "Oakland Store",
            "customer_feedback": long_feedback,
            "distance": 0.312345,
        },
        {
            "id": "F041",
            "store_name": "Omaha Store",
            "customer_feedback": "ice maker leaking water",
            "distance": 0.401,
        },
    ]
    pool, cursor = _mock_db_pool(rows=rows)
    tool = SemanticSearchTool(pool, openai_client=MagicMock())
    fake_vec = [0.0] * 1536
    with patch(
        "backend.agents.tools.semantic_search_tool.create_embedding_client"
    ) as mock_factory:
        mock_client = MagicMock()
        mock_client.embed_texts.return_value = [fake_vec]
        mock_factory.return_value = mock_client
        result = tool.execute(query_text="water leakage")

    assert result["success"] is True
    preview = result["top_preview"]
    assert preview["query_text"] == "water leakage"
    assert len(preview["matches"]) == 2
    assert len(preview["matches"]) <= 5
    assert preview["matches"][0]["rank"] == 1
    assert preview["matches"][0]["id"] == "F032"
    assert preview["matches"][0]["distance"] == 0.312
    assert preview["matches"][0]["store_name"] == "Oakland Store"
    assert len(preview["matches"][0]["feedback_snippet"]) <= 72
    assert preview["matches"][0]["feedback_snippet"].endswith("…")
