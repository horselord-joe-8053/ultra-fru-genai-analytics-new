from tools.cloud_shared.verify.verify_sse import (
    assert_no_semantic_after_first_hit,
    is_agent_disabled_by_config,
    is_non_retriable_query_error,
    is_semantic_hit,
    parse_sse_complete_answer,
    parse_sse_complete_data,
    parse_sse_error_message,
    parse_sse_events,
    parse_sse_tool_call_complete_events,
    semantic_search_completes,
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


def test_parse_sse_events_by_type():
    text = (
        "event: question\ndata: {\"question\": \"hi\"}\n\n"
        "event: tool_call_complete\ndata: {\"tool\": \"semantic_search\", \"output\": {\"success\": true, \"row_count\": 1}}\n\n"
    )
    events = parse_sse_events(text, "tool_call_complete")
    assert len(events) == 1
    assert events[0]["tool"] == "semantic_search"


def test_assert_no_semantic_after_first_hit_allows_retry_before_hit():
    events = [
        {"tool": "semantic_search", "output": {"success": False}},
        {"tool": "semantic_search", "output": {"success": True, "row_count": 3}},
    ]
    assert_no_semantic_after_first_hit(events)


def test_assert_no_semantic_after_first_hit_blocks_extra():
    events = [
        {"tool": "semantic_search", "output": {"success": True, "row_count": 1}},
        {"tool": "semantic_search", "output": {"success": True, "row_count": 2}},
    ]
    try:
        assert_no_semantic_after_first_hit(events)
        assert False, "expected AssertionError"
    except AssertionError:
        pass


def test_is_semantic_hit():
    assert is_semantic_hit({"output": {"success": True, "row_count": 1}})
    assert not is_semantic_hit({"output": {"success": True, "row_count": 0}})


def test_semantic_search_completes_filters_tool():
    text = (
        'event: tool_call_complete\ndata: {"tool": "generate_sql", "output": {}}\n\n'
        'event: tool_call_complete\ndata: {"tool": "semantic_search", "output": {"success": true, "row_count": 2}}\n\n'
    )
    events = semantic_search_completes(text)
    assert len(events) == 1
    assert events[0]["tool"] == "semantic_search"
