from unittest.mock import MagicMock

import pytest

from backend.agents.query_agent import QueryAgent
from backend.utils.display_truncate import (
    add_token_usage,
    get_exec_log_sql_preview_max_chars,
    is_executable_select_sql,
    is_sql_placeholder,
    normalize_token_usage,
    quote_for_exec_log,
    resolve_execute_sql,
    truncate_for_exec_log,
    unwrap_sql_literal,
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


def test_unwrap_sql_literal_single_quotes():
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    assert unwrap_sql_literal(f"'{sql}'") == sql


def test_unwrap_sql_literal_escapes_doubled_quotes():
    assert unwrap_sql_literal("'WHERE brand = ''Samsung'';'") == "WHERE brand = 'Samsung';"


def test_is_executable_select_sql_rejects_quoted_only_without_select_inside():
    assert is_executable_select_sql("'SELECT 1;'") is True
    assert is_executable_select_sql("[will use generate_sql]") is False


def test_resolve_execute_sql_unwraps_quoted_select():
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    assert resolve_execute_sql(f"'{sql}'", None) == sql


def test_resolve_execute_sql_backfills_from_generate_sql():
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    assert (
        resolve_execute_sql(
            "[will use the sql value returned from generate_sql]",
            sql,
        )
        == sql
    )


def test_quote_for_exec_log_wraps_in_single_quotes():
    assert quote_for_exec_log("SELECT 1;") == "'SELECT 1;'"


def test_quote_for_exec_log_escapes_apostrophe():
    assert quote_for_exec_log("WHERE brand = 'Samsung';") == "'WHERE brand = ''Samsung'';'"


def test_quote_for_exec_log_truncates_inside_quotes(monkeypatch):
    monkeypatch.setenv("EXEC_LOG_SQL_PREVIEW_MAX_CHARS", "10")
    quoted = quote_for_exec_log("abcdefghijklmnopqrstuvwxyz")
    assert quoted.startswith("'")
    assert quoted.endswith("'")
    assert "..." in quoted
    assert quoted == "'abcdefg...'"


def test_normalize_token_usage_claude_shape():
    assert normalize_token_usage({"input": 1, "output": 2, "total": 3}) == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
    }


def test_normalize_token_usage_normalized_shape():
    assert normalize_token_usage(
        {"input_tokens": 4, "output_tokens": 5, "total_tokens": 9}
    ) == {
        "input_tokens": 4,
        "output_tokens": 5,
        "total_tokens": 9,
    }


def test_normalize_token_usage_empty():
    assert normalize_token_usage(None) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_add_token_usage_accumulates():
    acc = {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
    assert add_token_usage(acc, {"input": 10, "output": 20, "total": 30}) == {
        "input_tokens": 11,
        "output_tokens": 22,
        "total_tokens": 33,
    }


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
    assert out["summary"].startswith("Generated SQL query: '")
    assert "SELECT AVG" in out["summary"]
    assert out["summary"].endswith("'")
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
    assert out["sql_query"].startswith("'SELECT AVG")
    assert out["sql_query"].endswith("'")


def test_apply_execute_sql_resolution_quoted_literal(query_agent):
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    normalized = {"sql": f"'{sql}'"}
    query_agent._apply_execute_sql_resolution(normalized, [])
    assert normalized["sql"] == sql


def test_apply_execute_sql_resolution_backfills_placeholder(query_agent):
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    normalized = {"sql": "[will use the sql value returned from generate_sql]"}
    tool_results = [
        {
            "tool": "generate_sql",
            "output": {"success": True, "sql": sql},
        }
    ]
    query_agent._apply_execute_sql_resolution(normalized, tool_results)
    assert normalized["sql"] == sql


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
    assert out["sql_query"].startswith("'SELECT AVG")


def test_build_sse_output_summary_generate_sql_includes_token_usage(query_agent):
    out = query_agent._build_sse_output_summary(
        "generate_sql",
        {
            "success": True,
            "sql": "SELECT 1;",
            "tokens": {"input": 7, "output": 3, "total": 10},
        },
    )
    assert out["token_usage"] == {
        "input_tokens": 7,
        "output_tokens": 3,
        "total_tokens": 10,
    }


def test_summarize_tool_result_unchanged_for_agent_context(query_agent):
    summary = query_agent._summarize_tool_result(
        {"success": True, "sql": "SELECT 1;"},
    )
    assert summary == "Generated SQL query"
