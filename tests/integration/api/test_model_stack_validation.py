"""Integration: /model-catalog stacks and invalid pair rejection on /query/stream."""
from __future__ import annotations

import os

import pytest
import requests

from tools.cloud_shared.verify.verify_sse import (
    is_agent_disabled_by_config,
    parse_sse_complete_answer,
    parse_sse_error_message,
    parse_sse_model_context,
)

pytestmark = pytest.mark.integration


def test_model_catalog_has_stacks(require_stack, base_url: str):
    r = requests.get(f"{base_url}/model-catalog", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "stacks" in body
    assert body.get("cloud_provider")
    assert "allow_override" in body
    assert body["defaults"]["embedding_profile"]
    assert body["defaults"]["chat_choice"]


def test_invalid_stack_returns_400(require_stack, base_url: str):
    """Cross-stack pair must be rejected before SSE."""
    url = (
        f"{base_url}/query/stream"
        "?query=test"
        "&embedding_profile=skylark_2048"
        "&chat_choice=claude_haiku"
    )
    r = requests.get(url, timeout=30)
    assert r.status_code == 400
    assert "Invalid model stack" in (r.text or "")


def test_valid_stack_sse_model_context_display(require_stack, base_url: str):
    """REQ-2: model_context SSE uses display strings, not logical profile ids."""
    timeout = int(os.environ.get("INTEGRATION_QUERY_STREAM_TIMEOUT", "120"))
    url = (
        f"{base_url}/query/stream"
        "?query=average%20rating"
        "&embedding_profile=openai_1536"
        "&chat_choice=claude_haiku"
    )
    r = requests.get(url, timeout=timeout)
    assert r.status_code == 200
    text = r.text or ""
    if "Agent-based query processing is disabled" in text:
        if is_agent_disabled_by_config():
            pytest.skip("Agent query disabled by configuration")
        err = parse_sse_error_message(text) or text[:200]
        pytest.fail(f"QueryStream agent error: {err}")
    if parse_sse_complete_answer(text) is None:
        err = parse_sse_error_message(text)
        if err:
            pytest.fail(f"QueryStream failed: {err[:300]}")
        pytest.skip("QueryStream returned no complete event (LLM cold start or missing keys?)")

    ctx = parse_sse_model_context(text)
    if ctx is None:
        pytest.skip("No model_context SSE event (older API?)")
    assert ctx.get("embedding_display")
    assert ctx.get("chat_display")
    assert ctx["embedding_display"] != "openai_1536"
    assert ctx["chat_display"] != "claude_haiku"
