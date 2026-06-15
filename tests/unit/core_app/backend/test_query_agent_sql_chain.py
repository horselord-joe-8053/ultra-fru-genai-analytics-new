from unittest.mock import MagicMock

import pytest

from backend.agents.query_agent import QueryAgent


@pytest.fixture
def query_agent():
    return QueryAgent(MagicMock(), MagicMock(), MagicMock())


def _mock_execute_success(sql_query=None, **_kwargs):
    sql = sql_query or _kwargs.get("sql", "")
    return {
        "success": True,
        "sql": sql,
        "rows": [{"n": 1}],
        "row_count": 1,
    }


def _mock_llm(monkeypatch, text: str):
    mock_llm = MagicMock()
    mock_llm.complete.return_value = {"text": text, "tokens": {}}
    monkeypatch.setattr(
        "backend.agents.query_agent.create_llm_client_for_choice",
        lambda _choice=None: mock_llm,
    )
    return mock_llm


def test_generate_sql_only_auto_chains_execute_in_same_iteration(
    query_agent, monkeypatch
):
    events: list[tuple[str, dict]] = []

    def callback(event_type, data):
        events.append((event_type, data))

    _mock_llm(
        monkeypatch,
        'TOOL: generate_sql\nINPUT: {"query": "count rows"}',
    )
    query_agent.tools["generate_sql"].execute = MagicMock(
        return_value={
            "success": True,
            "sql": "SELECT COUNT(*) FROM fru_sales_embeddings;",
        }
    )
    query_agent.tools["execute_sql"].execute = MagicMock(
        side_effect=_mock_execute_success
    )

    query_agent.process_query("count rows", progress_callback=callback)

    execute_calls = query_agent.tools["execute_sql"].execute.call_count
    assert execute_calls >= 1

    complete_tools = [
        data["tool"]
        for event_type, data in events
        if event_type == "tool_call_complete"
    ]
    gen_idx = complete_tools.index("generate_sql")
    exec_idx = complete_tools.index("execute_sql", gen_idx)
    assert exec_idx == gen_idx + 1


def test_planner_generate_then_execute_no_duplicate(
    query_agent, monkeypatch
):
    _mock_llm(
        monkeypatch,
        (
            'TOOL: generate_sql\nINPUT: {"query": "count rows"}\n'
            'TOOL: execute_sql\nINPUT: {"sql_query": "[from generate_sql]"}'
        ),
    )
    query_agent.tools["generate_sql"].execute = MagicMock(
        return_value={
            "success": True,
            "sql": "SELECT COUNT(*) FROM fru_sales_embeddings;",
        }
    )
    query_agent.tools["execute_sql"].execute = MagicMock(
        side_effect=_mock_execute_success
    )

    query_agent.process_query("count rows")

    assert query_agent.tools["execute_sql"].execute.call_count == 1


def test_failed_generate_sql_skips_auto_execute(query_agent, monkeypatch):
    _mock_llm(
        monkeypatch,
        'TOOL: generate_sql\nINPUT: {"query": "count rows"}',
    )
    query_agent.tools["generate_sql"].execute = MagicMock(
        return_value={"success": False, "error": "LLM failed"}
    )
    query_agent.tools["execute_sql"].execute = MagicMock()

    query_agent.process_query("count rows")

    query_agent.tools["execute_sql"].execute.assert_not_called()


def test_planner_execute_sql_placeholder_still_resolved(query_agent, monkeypatch):
    sql = "SELECT AVG(feedback_rating) FROM fru_sales_embeddings;"
    _mock_llm(
        monkeypatch,
        (
            'TOOL: generate_sql\nINPUT: {"query": "average rating"}\n'
            'TOOL: execute_sql\nINPUT: {"sql_query": "[will use generate_sql]"}'
        ),
    )
    query_agent.tools["generate_sql"].execute = MagicMock(
        return_value={"success": True, "sql": sql}
    )

    executed_sql: list[str] = []

    def capture_execute(**kwargs):
        executed_sql.append(kwargs.get("sql") or kwargs.get("sql_query", ""))
        return _mock_execute_success(**kwargs)

    query_agent.tools["execute_sql"].execute = MagicMock(side_effect=capture_execute)

    query_agent.process_query("average rating")

    assert executed_sql
    assert executed_sql[0] == sql
