"""
Integration: semantic_search SSE contract (query_text, early break, event order).

Prerequisite: local API with agent + LLM keys (same as test_exec_log_sse.py).
"""
from __future__ import annotations

import os
import re

import pytest
import requests

from tools.cloud_shared.verify.verify_sse import (
    _iter_sse_events,
    assert_no_semantic_after_first_hit,
    first_event_index,
    is_agent_disabled_by_config,
    is_semantic_hit,
    parse_sse_complete_answer,
    parse_sse_error_message,
    parse_sse_events,
    parse_sse_tool_call_complete_events,
    semantic_search_completes,
)

pytestmark = pytest.mark.integration

SEMANTIC_QUERY = "complaints%20about%20water%20leaks"
SQL_QUERY = "average%20rating"


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


def _semantic_events(text: str) -> list[dict]:
    return [
        e
        for e in parse_sse_tool_call_complete_events(text)
        if e.get("tool") == "semantic_search"
    ]


def test_semantic_search_sse_includes_query_text(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, SEMANTIC_QUERY)
    _skip_if_agent_unavailable(text)

    events = _semantic_events(text)
    if not events:
        pytest.skip("No semantic_search tool_call_complete in stream")

    for event in events:
        inp = event.get("input") or {}
        query_text = inp.get("query_text") or inp.get("effective_query_text") or ""
        if inp.get("query_text_source") == "fallback_question" or not inp.get("filters"):
            assert re.search(r"water|leak", query_text, re.I), inp


def test_no_semantic_search_after_first_hit(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, SEMANTIC_QUERY)
    _skip_if_agent_unavailable(text)

    events = semantic_search_completes(text)
    if not any(is_semantic_hit(e) for e in events):
        pytest.skip("no successful semantic_search this run")

    assert_no_semantic_after_first_hit(events)


def test_planning_start_before_plan_complete(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, SQL_QUERY)
    _skip_if_agent_unavailable(text)

    planning_start_idx = None
    plan_complete_idx = None
    for idx, (event_type, data) in enumerate(_iter_sse_events(text)):
        if (
            event_type == "tool_call_start"
            and data.get("tool") == "pseudo_tool#llm_plan"
            and planning_start_idx is None
        ):
            planning_start_idx = idx
        if (
            event_type == "tool_call_complete"
            and data.get("tool") == "pseudo_tool#llm_plan"
            and plan_complete_idx is None
        ):
            plan_complete_idx = idx

    if planning_start_idx is None or plan_complete_idx is None:
        pytest.skip("Planning SSE events missing (older API?)")

    assert planning_start_idx < plan_complete_idx


def test_iteration_start_before_first_tool_complete(require_stack, base_url: str):
    text = _fetch_query_stream(base_url, SQL_QUERY)
    _skip_if_agent_unavailable(text)

    iter_idx = first_event_index(text, "iteration_start")
    complete_idx = first_event_index(text, "tool_call_complete")
    if iter_idx is None or complete_idx is None:
        pytest.skip("Missing iteration_start or tool_call_complete")
    assert iter_idx < complete_idx
