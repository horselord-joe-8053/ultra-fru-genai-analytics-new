from tools.cloud_shared.verify.verify_sse import (
    is_agent_disabled_by_config,
    is_non_retriable_query_error,
    parse_sse_complete_answer,
    parse_sse_complete_data,
    parse_sse_error_message,
    parse_sse_tool_call_complete_events,
)


def test_parse_sse_complete_answer():
    text = 'event: complete\ndata: {"answer": "hello"}\n\n'
    assert parse_sse_complete_answer(text) == "hello"


def test_parse_sse_complete_data():
    text = 'event: complete\ndata: {"answer": "hello", "token_usage": {"total_tokens": 9}}\n\n'
    assert parse_sse_complete_data(text) == {
        "answer": "hello",
        "token_usage": {"total_tokens": 9},
    }


def test_parse_sse_tool_call_complete_events():
    text = (
        'event: tool_call_complete\ndata: {"tool": "generate_sql", "output": {"summary": "x"}}\n\n'
        'event: tool_call_complete\ndata: {"tool": "execute_sql", "input": {"sql_query": "\'SELECT 1\'"}}\n\n'
    )
    events = parse_sse_tool_call_complete_events(text)
    assert len(events) == 2
    assert events[0]["tool"] == "generate_sql"
    assert events[1]["tool"] == "execute_sql"


def test_parse_sse_error_message():
    text = 'event: error\ndata: {"message": "boom"}\n\n'
    assert parse_sse_error_message(text) == "boom"


def test_is_non_retriable_model_not_found():
    assert is_non_retriable_query_error("not_found_error model: x 404")


def test_is_agent_disabled_by_config(monkeypatch):
    monkeypatch.setenv("USE_AGENT_QUERY", "false")
    assert is_agent_disabled_by_config() is True
