"""
Integration: HTTP query path against a running local API (Docker / orchestrator deploy).

Prerequisite: `python orchestrator.py deploy --provider local --scope all` (or API on INTEGRATION_API_BASE_URL).
"""
from __future__ import annotations

import os

import pytest
import requests

from tools.cloud_shared.verify.verify_sse import (
    is_agent_disabled_by_config,
    parse_sse_complete_answer,
    parse_sse_error_message,
)

pytestmark = pytest.mark.integration


def test_health_returns_ok(require_stack, base_url: str):
    r = requests.get(f"{base_url}/health", timeout=10)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_version_returns_version_list(require_stack, base_url: str):
    r = requests.get(f"{base_url}/version", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert isinstance(data["version"], list)


def test_query_stream_smoke(require_stack, base_url: str, total_rec: int | None):
    """SSE /query/stream: accept complete answer, agent disabled, or skip when no LLM keys."""
    timeout = int(os.environ.get("INTEGRATION_QUERY_STREAM_TIMEOUT", "120"))
    url = f"{base_url}/query/stream?query=total%20number%20of%20record"
    r = requests.get(url, timeout=timeout)
    assert r.status_code == 200

    if "Agent-based query processing is disabled" in (r.text or ""):
        if is_agent_disabled_by_config() or "disabled by configuration" in (r.text or "").lower():
            return
        err = parse_sse_error_message(r.text) or r.text[:200]
        pytest.fail(f"QueryStream agent error: {err}")

    answer = parse_sse_complete_answer(r.text)
    if answer is None:
        err = parse_sse_error_message(r.text)
        if err:
            pytest.fail(f"QueryStream failed: {err[:300]}")
        pytest.skip("QueryStream returned no complete event (LLM cold start or missing keys?)")

    if total_rec is not None and str(total_rec) not in answer:
        pytest.fail(f"Answer missing expected total_rec={total_rec}: {answer[:200]}...")


def test_analytics_endpoint_responds(require_stack, base_url: str):
    """Analytics may return 'no data yet' before first Spark run; we only require HTTP 200 + JSON."""
    r = requests.get(f"{base_url}/analytics", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    if data.get("error") and "No analytics data available yet" in data["error"]:
        return
    if data.get("error"):
        pytest.fail(f"Analytics error: {data['error']}")
