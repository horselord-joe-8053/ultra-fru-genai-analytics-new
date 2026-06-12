from unittest.mock import MagicMock

import pytest

from backend.agents.query_agent import QueryAgent
from backend.utils.display_truncate import (
    get_exec_log_sql_preview_max_chars,
    is_sql_placeholder,
    truncate_for_exec_log,
)


def test_truncate_for_exec_log_no_limit():
    text = "SELECT * FROM fru_sales_embeddings;"
    assert truncate_for_exec_log(text, 0) == text


def test_truncate_for_exec_log_with_ellipsis():
    text = "abcdefghijklmnopqrstuvwxyz"
    assert truncate_for_exec_log(text, 10) == "abcdefg..."


def test_get_exec_log_sql_preview_max_chars_default(monkeypatch):
    monkeypatch.delenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", raising=False)
    assert get_exec_log_sql_preview_max_chars() == 150


def test_get_exec_log_sql_preview_max_chars_invalid(monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "not-a-number")
    assert get_exec_log_sql_preview_max_chars() == 150


def test_get_exec_log_sql_preview_max_chars_zero(monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "0")
    assert get_exec_log_sql_preview_max_chars() == 0


def test_get_exec_log_sql_preview_max_chars_clamp(monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "9999")
    assert get_exec_log_sql_preview_max_chars() == 500


@pytest.mark.parametrize(
    "value,expected",
    [
        ("[The sql value from generate_sql output]", True),
        ("[will use the sql value returned from generate_sql]", True),
        ("SELECT AVG(x) FROM t;", False),
        ("", True),
    ],
)
def test_is_sql_placeholder(value, expected):
    assert is_sql_placeholder(value) is expected


@pytest.fixture
def query_agent():
    return QueryAgent(MagicMock(), MagicMock(), MagicMock())


def test_build_sse_output_summary_generate_sql(query_agent, monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "20")
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    out = query_agent._build_sse_output_summary(
        "generate_sql",
        {"success": True, "sql": sql},
    )
    assert out["summary"].startswith("Generated SQL query:")
    assert "SELECT AVG" in out["summary"]
    assert out["sql"] == sql


def test_build_sse_tool_input_execute_sql_replaces_placeholder(query_agent, monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "50")
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    out = query_agent._build_sse_tool_input(
        "execute_sql",
        {"sql_query": "[The sql value from generate_sql output]"},
        {"sql_query": sql},
        {"success": True, "sql": sql},
    )
    assert "[The sql" not in out["sql_query"]
    assert out["sql_query"].startswith("SELECT AVG")


def test_build_sse_tool_input_execute_sql_uses_prior_generate_sql(query_agent, monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "50")
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    out = query_agent._build_sse_tool_input(
        "execute_sql",
        {"sql_query": "[will use the sql value returned from generate_sql]"},
        {"sql_query": "[will use the sql value returned from generate_sql]"},
        {"success": False, "error": "Only SELECT queries are allowed"},
        prior_generate_sql=sql,
    )
    assert "will use" not in out["sql_query"]
    assert out["sql_query"].startswith("SELECT AVG")


def test_summarize_tool_result_unchanged_for_agent_context(query_agent):
    summary = query_agent._summarize_tool_result(
        {"success": True, "sql": "SELECT 1;"},
    )
    assert summary == "Generated SQL query"
