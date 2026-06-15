"""Unit tests for semantic_search normalization and SSE input builder."""
from unittest.mock import MagicMock

import pytest

from backend.agents.query_agent import QueryAgent


@pytest.fixture
def agent():
    return QueryAgent(db_pool=MagicMock(), llm_client=MagicMock(), openai_client=MagicMock())


def test_normalize_semantic_search_fallback_query_text(agent):
    agent._current_question = "complaints about water leaks"
    normalized = agent._normalize_tool_input(
        "semantic_search",
        {"feedback_sentiment_category": "Negative"},
    )
    assert normalized["query_text"] == "complaints about water leaks"
    assert normalized["filters"]["feedback_sentiment_category"] == ["Negative"]


def test_build_sse_semantic_includes_query_text_and_source(agent):
    agent._current_question = "water leaks"
    tool_input = {"feedback_sentiment_category": "Negative"}
    normalized = agent._normalize_tool_input("semantic_search", tool_input)
    sse = agent._build_sse_tool_input(
        "semantic_search",
        tool_input,
        normalized,
        {"success": True, "row_count": 5},
    )
    assert sse["query_text"] == "water leaks"
    assert sse["query_text_source"] == "fallback_question"
    assert "filters" in sse


def test_build_sse_semantic_output_includes_top_preview(agent):
    preview = {
        "query_text": "water leakage",
        "matches": [
            {
                "rank": 1,
                "id": "F032",
                "distance": 0.31,
                "store_name": "Oakland Store",
                "feedback_snippet": "water leaking from dispenser",
            }
        ],
    }
    out = agent._build_sse_output_summary(
        "semantic_search",
        {"success": True, "row_count": 50, "top_preview": preview},
    )
    assert out["top_preview"] == preview
    assert "top 1 matches" in out["summary"]


def test_semantic_fingerprint_stable(agent):
    a = agent._semantic_search_fingerprint(
        {"query_text": "x", "filters": {"brand": ["A"]}, "limit": 50}
    )
    b = agent._semantic_search_fingerprint(
        {"query_text": "x", "filters": {"brand": ["A"]}, "limit": 50}
    )
    assert a == b


def _mock_llm(monkeypatch, responses: list[dict]):
    call_idx = {"n": 0}

    def fake_complete(*_args, **_kwargs):
        idx = min(call_idx["n"], len(responses) - 1)
        call_idx["n"] += 1
        return responses[idx]

    mock_llm = MagicMock()
    mock_llm.complete.side_effect = fake_complete
    monkeypatch.setattr(
        "backend.agents.query_agent.create_llm_client_for_choice",
        lambda _choice=None: mock_llm,
    )


def _semantic_plan_response():
    return {
        "text": (
            'TOOL: semantic_search\n'
            'INPUT: {"feedback_sentiment_category": "Negative"}'
        ),
        "tokens": {"input": 1, "output": 1, "total": 2},
    }


def _count_semantic_complete(events: list[tuple[str, dict]]) -> int:
    return sum(
        1
        for et, data in events
        if et == "tool_call_complete" and data.get("tool") == "semantic_search"
    )


def test_early_break_after_semantic_hit(agent, monkeypatch):
    semantic_calls = {"n": 0}

    def fake_semantic(**_kwargs):
        semantic_calls["n"] += 1
        return {"success": True, "row_count": 5, "results": []}

    agent.tools["semantic_search"].execute = fake_semantic
    _mock_llm(
        monkeypatch,
        [_semantic_plan_response(), {"text": "Done.", "tokens": {"input": 1, "output": 1, "total": 2}}],
    )
    events: list[tuple[str, dict]] = []
    agent.process_query("water leaks", progress_callback=lambda t, d: events.append((t, d)))
    assert semantic_calls["n"] == 1
    assert _count_semantic_complete(events) == 1


def test_semantic_retry_before_hit(agent, monkeypatch):
    semantic_calls = {"n": 0}

    def fake_semantic(**_kwargs):
        semantic_calls["n"] += 1
        if semantic_calls["n"] == 1:
            return {"success": False, "error": "mock fail", "row_count": 0}
        return {"success": True, "row_count": 3, "results": []}

    agent.tools["semantic_search"].execute = fake_semantic
    _mock_llm(
        monkeypatch,
        [
            _semantic_plan_response(),
            _semantic_plan_response(),
            {"text": "Done.", "tokens": {"input": 1, "output": 1, "total": 2}},
        ],
    )
    events: list[tuple[str, dict]] = []
    agent.process_query("water leaks", progress_callback=lambda t, d: events.append((t, d)))
    assert semantic_calls["n"] == 2
    assert _count_semantic_complete(events) == 2


def test_no_early_break_on_empty_semantic_rows(agent, monkeypatch):
    semantic_calls = {"n": 0}

    def fake_semantic(**_kwargs):
        semantic_calls["n"] += 1
        return {"success": True, "row_count": 0, "results": []}

    agent.tools["semantic_search"].execute = fake_semantic
    _mock_llm(
        monkeypatch,
        [
            _semantic_plan_response(),
            {"text": "No more tools.", "tokens": {"input": 1, "output": 1, "total": 2}},
            {"text": "Done.", "tokens": {"input": 1, "output": 1, "total": 2}},
        ],
    )
    events: list[tuple[str, dict]] = []
    agent.process_query("water leaks", progress_callback=lambda t, d: events.append((t, d)))
    assert semantic_calls["n"] >= 1
    assert _count_semantic_complete(events) >= 1

