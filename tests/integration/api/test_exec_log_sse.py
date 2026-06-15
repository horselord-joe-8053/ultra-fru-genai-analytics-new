"""
Integration: Execution Log SSE shape (quoted SQL, normalized token usage).

Prerequisite: local API with agent + LLM keys (same as test_query_flow.py).
"""
from __future__ import annotations

import os

import pytest
import requests

from tools.cloud_shared.verify.verify_sse import (
    is_agent_disabled_by_config,
    parse_sse_complete_answer,
    parse_sse_complete_data,
    parse_sse_error_message,
    parse_sse_tool_call_complete_events,
)

pytestmark = pytest.mark.integration

LLM_STEP_TOOLS = frozenset(
    {
        "pseudo_tool#llm_plan",
        "generate_sql",
        "pseudo_tool#llm_synthesize_answer",
    }
)


def _fetch_query_stream(base_url: str, query: str) -> str:
    timeout = int(os.environ.get("INTEGRATION_QUERY_STREAM_TIMEOUT", "120"))
    url = f"{base_url}/query/stream?query={query}"
    r = requests.get(url, timeout=timeout)
    assert r.status_code == 200
    return r.text or ""


def _skip_if_agent_unavailable(text: str) -> None:
    if "Agent-based query processing is disabled" in text:
        if is_agent_disabled_by_config() or "disabled by configuration" in text.lower():
            pytest.skip("Agent query disabled by configuration")
        err = parse_sse_error_message(text) or text[:200]
        pytest.fail(f"QueryStream agent error: {err}")

    if parse_sse_complete_answer(text) is None:
        err = parse_sse_error_message(text)
        if err:
            pytest.fail(f"QueryStream failed: {err[:300]}")
        pytest.skip("QueryStream returned no complete event (LLM cold start or missing keys?)")


def test_query_stream_generate_sql_summary_quoted(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, "average%20rating")
    _skip_if_agent_unavailable(text)

    gen_events = [
        e
        for e in parse_sse_tool_call_complete_events(text)
        if e.get("tool") == "generate_sql"
    ]
    if not gen_events:
        pytest.skip("No generate_sql tool_call_complete in stream")

    summary = (gen_events[0].get("output") or {}).get("summary") or ""
    assert summary.startswith("Generated SQL query: '"), summary[:120]
    assert summary.endswith("'"), summary[:120]


def test_query_stream_execute_sql_input_quoted(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, "average%20rating")
    _skip_if_agent_unavailable(text)

    exec_events = [
        e
        for e in parse_sse_tool_call_complete_events(text)
        if e.get("tool") == "execute_sql"
    ]
    if not exec_events:
        pytest.skip("No execute_sql tool_call_complete in stream")

    sql_query = (exec_events[0].get("input") or {}).get("sql_query") or ""
    assert sql_query.startswith("'"), sql_query[:120]
    assert "SELECT" in sql_query.upper()
    assert "[will use" not in sql_query.lower()


def test_query_stream_token_usage_normalized_on_llm_steps(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, "average%20rating")
    _skip_if_agent_unavailable(text)

    tool_events = parse_sse_tool_call_complete_events(text)
    plan_rows = [e for e in tool_events if e.get("tool") == "pseudo_tool#llm_plan"]
    if not plan_rows:
        pytest.skip("No pseudo_tool#llm_plan events (older API image?)")

    for event in tool_events:
        tool = event.get("tool")
        if tool not in LLM_STEP_TOOLS:
            continue
        usage = (event.get("output") or {}).get("token_usage")
        if not usage:
            continue
        assert "input_tokens" in usage, usage
        assert "output_tokens" in usage, usage
        assert "total_tokens" in usage, usage
        assert "input" not in usage, usage

    synth_rows = [
        e for e in tool_events if e.get("tool") == "pseudo_tool#llm_synthesize_answer"
    ]
    if synth_rows and (synth_rows[0].get("output") or {}).get("token_usage"):
        assert synth_rows[0]["output"]["token_usage"]["total_tokens"] > 0


def test_query_stream_complete_token_usage_is_run_total(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, "average%20rating")
    _skip_if_agent_unavailable(text)

    tool_events = parse_sse_tool_call_complete_events(text)
    complete = parse_sse_complete_data(text)
    assert complete is not None
    complete_usage = complete.get("token_usage") or {}

    llm_sum = 0
    for event in tool_events:
        if event.get("tool") not in LLM_STEP_TOOLS:
            continue
        usage = (event.get("output") or {}).get("token_usage") or {}
        llm_sum += int(usage.get("total_tokens") or 0)

    assert int(complete_usage.get("total_tokens") or 0) == llm_sum


def test_query_stream_execute_sql_no_token_usage_or_zero(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, "average%20rating")
    _skip_if_agent_unavailable(text)

    exec_events = [
        e
        for e in parse_sse_tool_call_complete_events(text)
        if e.get("tool") == "execute_sql"
    ]
    if not exec_events:
        pytest.skip("No execute_sql tool_call_complete in stream")

    for event in exec_events:
        usage = (event.get("output") or {}).get("token_usage")
        if usage is None:
            continue
        assert int(usage.get("total_tokens") or 0) == 0


def test_post_query_token_usage_normalized(require_stack, base_url: str):
    """POST /query returns the same normalized token_usage shape as SSE complete (parity in unit tests)."""
    query = "total number of record"
    timeout = int(os.environ.get("INTEGRATION_QUERY_STREAM_TIMEOUT", "120"))

    post = requests.post(
        f"{base_url}/query",
        json={"query": query},
        timeout=timeout,
    )
    assert post.status_code == 200
    body = post.json() or {}
    usage = body.get("token_usage") or {}
    assert "input_tokens" in usage, usage
    assert "output_tokens" in usage, usage
    assert "total_tokens" in usage, usage
    assert "input" not in usage, usage
    assert int(usage.get("total_tokens") or 0) > 0
