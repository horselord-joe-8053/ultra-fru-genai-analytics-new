from unittest.mock import MagicMock

import pytest

from backend.agents.query_agent import QueryAgent


@pytest.fixture
def query_agent():
    return QueryAgent(MagicMock(), MagicMock(), MagicMock())


def test_process_query_emits_normalized_token_usage_and_run_total(
    query_agent, monkeypatch
):
    events: list[tuple[str, dict]] = []

    def callback(event_type, data):
        events.append((event_type, data))

    claude_calls = [
        {
            "text": 'TOOL: generate_sql\nINPUT: {"query": "count rows"}',
            "tokens": {"input": 10, "output": 20, "total": 30},
        },
        {
            "text": "No more tools needed.",
            "tokens": {"input": 5, "output": 5, "total": 10},
        },
        {
            "text": "There are 100 rows.",
            "tokens": {"input": 100, "output": 50, "total": 150},
        },
    ]
    call_idx = {"n": 0}

    def fake_complete(*_args, **_kwargs):
        idx = min(call_idx["n"], len(claude_calls) - 1)
        call_idx["n"] += 1
        return claude_calls[idx]

    mock_llm = MagicMock()
    mock_llm.complete.side_effect = fake_complete
    monkeypatch.setattr(
        "backend.agents.query_agent.create_llm_client_for_choice",
        lambda _choice=None: mock_llm,
    )
    query_agent.tools["generate_sql"].execute = MagicMock(
        return_value={
            "success": True,
            "sql": "SELECT COUNT(*) FROM fru_sales_embeddings;",
            "tokens": {"input": 40, "output": 5, "total": 45},
        }
    )

    result = query_agent.process_query("count rows", progress_callback=callback)

    tool_events = [data for event_type, data in events if event_type == "tool_call_complete"]
    plan_rows = [e for e in tool_events if e["tool"] == "pseudo_tool#llm_plan"]
    assert len(plan_rows) >= 1
    assert plan_rows[0]["output"]["token_usage"] == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
    }

    gen_rows = [e for e in tool_events if e["tool"] == "generate_sql"]
    assert gen_rows[0]["output"]["token_usage"]["total_tokens"] == 45

    synth_rows = [
        e for e in tool_events if e["tool"] == "pseudo_tool#llm_synthesize_answer"
    ]
    assert synth_rows[0]["output"]["token_usage"] == {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }
    assert "input" not in synth_rows[0]["output"]["token_usage"]

    expected_total = 30 + 10 + 45 + 150
    complete_events = [data for event_type, data in events if event_type == "complete"]
    assert complete_events[0]["token_usage"]["total_tokens"] == expected_total
    assert result["token_usage"]["total_tokens"] == expected_total
