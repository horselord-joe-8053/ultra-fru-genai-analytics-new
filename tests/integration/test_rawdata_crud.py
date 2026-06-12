"""
Integration: Data Management CRUD via /rawdata (same API the UI uses).

Prerequisite: local API + Postgres + OpenAI keys (orchestrator nonkube deploy).
"""
from __future__ import annotations

import uuid

import pytest
import requests

pytestmark = pytest.mark.integration


def _sample_record(record_id: str) -> dict:
    return {
        "id": record_id,
        "customer_id": f"CUST_{record_id}",
        "brand": "Samsung",
        "fridge_model": "RFXSPACEX",
        "capacity_liters": 28,
        "price": 50000,
        "sales_date": "2026-05-12",
        "store_name": "New York Store",
        "store_address": "22 Broadway, New York, NY 10001",
        "customer_feedback": "Integration test feedback for embedding sync",
        "feedback_rating": 9,
        "feedback_sentiment_category": "Positive",
    }


def _skip_if_embed_config_error(resp: requests.Response) -> None:
    if resp.status_code in (200, 201):
        return
    try:
        err = (resp.json() or {}).get("error", "")
    except ValueError:
        err = resp.text or ""
    if "OPENAI_EMBED_MODEL" in err or "OPENAI_API_KEY" in err:
        pytest.skip(f"OpenAI embedding not configured in API container: {err[:200]}")
    if "Failed to generate embedding" in err:
        pytest.skip(f"Embedding API unavailable: {err[:200]}")


def test_rawdata_crud_lifecycle(require_stack, base_url: str):
    """Create, read, update, list, delete — mirrors Data Management UI flow."""
    record_id = f"F_CRUD_{uuid.uuid4().hex[:8].upper()}"
    payload = _sample_record(record_id)
    timeout = 60

    # Create (POST /rawdata) — triggers OpenAI embedding sync
    r = requests.post(f"{base_url}/rawdata", json=payload, timeout=timeout)
    _skip_if_embed_config_error(r)
    assert r.status_code == 201, r.text
    assert r.json().get("id") == record_id

    try:
        # Read (GET /rawdata/<id>)
        r = requests.get(f"{base_url}/rawdata/{record_id}", timeout=timeout)
        assert r.status_code == 200
        row = r.json()
        assert row["id"] == record_id
        assert row["brand"] == "Samsung"
        assert row["customer_feedback"] == payload["customer_feedback"]

        # Update (PUT /rawdata/<id>)
        updated_feedback = "Updated integration test feedback"
        r = requests.put(
            f"{base_url}/rawdata/{record_id}",
            json={**payload, "customer_feedback": updated_feedback, "price": 51000},
            timeout=timeout,
        )
        _skip_if_embed_config_error(r)
        assert r.status_code == 200
        r = requests.get(f"{base_url}/rawdata/{record_id}", timeout=timeout)
        assert r.json()["customer_feedback"] == updated_feedback
        assert float(r.json()["price"]) == 51000

        # List (GET /rawdata) — record appears in paginated results
        r = requests.get(f"{base_url}/rawdata?limit=500&offset=0", timeout=timeout)
        assert r.status_code == 200
        data = r.json()
        ids = {item["id"] for item in data.get("items", [])}
        assert record_id in ids
    finally:
        # Delete (DELETE /rawdata/<id>)
        r = requests.delete(f"{base_url}/rawdata/{record_id}", timeout=timeout)
        assert r.status_code == 200

    r = requests.get(f"{base_url}/rawdata/{record_id}", timeout=timeout)
    assert r.status_code == 404


def test_rawdata_create_requires_id(require_stack, base_url: str):
    r = requests.post(f"{base_url}/rawdata", json={"brand": "GE"}, timeout=30)
    assert r.status_code == 400
    assert "id" in (r.json().get("error") or "").lower()
