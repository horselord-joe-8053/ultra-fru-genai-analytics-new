"""
Integration: reuse tools.cloud_shared.verify against the local API (same as orchestrator verify).

Smoke mode checks Health + Version only. Set INTEGRATION_FULL_VERIFY=1 to poll QueryStream and Analytics
(requires DB/ETL and CSV row count; see tools/local/scope_shared/verify/verify_all_deploy.py).
"""
from __future__ import annotations

import os

import pytest

from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints

pytestmark = pytest.mark.integration


def _integration_verify_timeout() -> int:
    return int(os.environ.get("INTEGRATION_VERIFY_TIMEOUT_SEC", "90"))


def test_verify_api_endpoints_smoke(require_stack, base_url: str):
    ok, rows = verify_api_endpoints(
        base_url=base_url,
        total_rec=0,
        scope="nonkube",
        provider="local",
        timeout_secs=_integration_verify_timeout(),
        heartbeat_interval_sec=5,
        query_stream_timeout_sec=30,
        skip_frontend=True,
        endpoint_names=["Health", "Version"],
    )
    assert ok, [f"{r.endpoint}: {r.notes}" for r in rows if not r.ok]


def _full_verify_enabled() -> bool:
    return os.environ.get("INTEGRATION_FULL_VERIFY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


@pytest.mark.skipif(
    not _full_verify_enabled(),
    reason="Set INTEGRATION_FULL_VERIFY=1 to run full verify (QueryStream + Analytics)",
)
def test_verify_api_endpoints_full(require_stack, base_url: str, total_rec: int | None):
    if total_rec is None:
        pytest.skip(
            "INTEGRATION_FULL_VERIFY requires core_app/data/raw/fridge_sales_with_rating.csv "
            "or INTEGRATION_TOTAL_REC"
        )
    ok, rows = verify_api_endpoints(
        base_url=base_url,
        total_rec=total_rec,
        scope="nonkube",
        provider="local",
        timeout_secs=int(os.environ.get("INTEGRATION_VERIFY_TIMEOUT_SEC", "300")),
        heartbeat_interval_sec=10,
        skip_frontend=True,
    )
    assert ok, [f"{r.endpoint}: {r.notes}" for r in rows if not r.ok]
