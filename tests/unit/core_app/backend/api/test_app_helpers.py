import json
from datetime import date, datetime
from decimal import Decimal

from backend.api.app import (
    _json_safe,
    build_claude_system_prompt,
    build_claude_user_payload,
    is_qualitative,
    validate_query,
)


def test_validate_query_empty():
    ok, err = validate_query("   ")
    assert not ok
    assert "empty" in err.lower()


def test_validate_query_too_long():
    ok, err = validate_query("x" * 1001)
    assert not ok
    assert "long" in err.lower()


def test_validate_query_ok():
    ok, err = validate_query("How many sales?")
    assert ok and err is None


def test_is_qualitative_quantitative_wins():
    assert is_qualitative("how many complaints") is False


def test_is_qualitative_keyword():
    assert is_qualitative("why are customers unhappy") is True


def test_json_safe_decimal_and_dates():
    payload = _json_safe({"d": Decimal("1.5"), "t": datetime(2026, 1, 1, 12, 0, 0), "day": date(2026, 1, 2)})
    assert payload["d"] == 1.5
    assert "2026" in payload["t"]
    assert "2026-01-02" in payload["day"]


def test_build_claude_user_payload():
    body = build_claude_user_payload("q", [{"id": 1, "price": Decimal("9.99")}])
    data = json.loads(body)
    assert data["question"] == "q"
    assert data["sample_records"][0]["price"] == 9.99


def test_build_claude_system_prompt_non_empty():
    assert "FRU" in build_claude_system_prompt()
