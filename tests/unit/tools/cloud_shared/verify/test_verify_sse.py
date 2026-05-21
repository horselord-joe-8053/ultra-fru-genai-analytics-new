from tools.cloud_shared.verify.verify_sse import (
    is_agent_disabled_by_config,
    is_non_retriable_query_error,
    parse_sse_complete_answer,
    parse_sse_error_message,
)


def test_parse_sse_complete_answer():
    text = 'event: complete\ndata: {"answer": "hello"}\n\n'
    assert parse_sse_complete_answer(text) == "hello"


def test_parse_sse_error_message():
    text = 'event: error\ndata: {"message": "boom"}\n\n'
    assert parse_sse_error_message(text) == "boom"


def test_is_non_retriable_model_not_found():
    assert is_non_retriable_query_error("not_found_error model: x 404")


def test_is_agent_disabled_by_config(monkeypatch):
    monkeypatch.setenv("USE_AGENT_QUERY", "false")
    assert is_agent_disabled_by_config() is True
