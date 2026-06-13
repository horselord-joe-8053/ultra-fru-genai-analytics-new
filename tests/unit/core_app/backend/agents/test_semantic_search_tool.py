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
