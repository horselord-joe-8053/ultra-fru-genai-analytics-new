"""
Integration test fixtures: live local API (Docker / orchestrator deploy).

Skips when the stack is not reachable so `pytest -m "not integration"` stays the default PR path.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def integration_base_url() -> str:
    explicit = os.environ.get("INTEGRATION_API_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    port = os.environ.get("LOCAL_SERVER_PORT", "5001").strip() or "5001"
    return f"http://localhost:{port}"


def stack_is_up(base_url: str, timeout_sec: float = 3.0) -> bool:
    try:
        r = requests.get(f"{base_url.rstrip('/')}/health", timeout=timeout_sec)
        return r.status_code == 200
    except (requests.RequestException, OSError):
        return False


def expected_total_rec_from_csv() -> int | None:
    csv_path = REPO_ROOT / "core_app" / "data" / "raw" / "fridge_sales_with_rating.csv"
    if not csv_path.is_file():
        return None
    with csv_path.open() as f:
        return max(0, sum(1 for _ in f) - 1)


@pytest.fixture(scope="session")
def base_url() -> str:
    return integration_base_url()


@pytest.fixture(scope="session")
def require_stack(base_url: str):
    if not stack_is_up(base_url):
        pytest.skip(
            "Local API not reachable. Start Docker and run: "
            "python orchestrator.py deploy --provider local --scope all "
            f"(expected {base_url}/health)"
        )
    return base_url


@pytest.fixture(scope="session")
def total_rec() -> int | None:
    env_val = os.environ.get("INTEGRATION_TOTAL_REC", "").strip()
    if env_val.isdigit():
        return int(env_val)
    return expected_total_rec_from_csv()
