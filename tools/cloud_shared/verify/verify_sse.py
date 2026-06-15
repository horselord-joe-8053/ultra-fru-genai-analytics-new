"""
SSE parsing and QueryStream helpers for verification.

Used by verify_api_endpoints to parse /query/stream responses and classify errors.
"""
import json
import os


def _iter_sse_events(text: str):
    """Yield (event_type, data_json) for each SSE block in text."""
    for block in text.split("\n\n"):
        event_type = None
        data_json = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data_json = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    pass
        if event_type and data_json is not None:
            yield event_type, data_json


def parse_sse_tool_call_complete_events(text: str) -> list[dict]:
    """Parse SSE stream; return data dicts from tool_call_complete events."""
    return [
        data
        for event_type, data in _iter_sse_events(text)
        if event_type == "tool_call_complete"
    ]


def parse_sse_complete_data(text: str) -> dict | None:
    """Parse SSE stream; return data dict from last event: complete."""
    last = None
    for event_type, data in _iter_sse_events(text):
        if event_type == "complete":
            last = data
    return last


def parse_sse_complete_answer(text: str) -> str | None:
    """Parse SSE stream; return answer from last event: complete data."""
    last_answer = None
    for event_type, data_json in _iter_sse_events(text):
        if event_type == "complete" and "answer" in data_json:
            last_answer = data_json.get("answer", "")
    return last_answer


def parse_sse_error_message(text: str) -> str | None:
    """Parse SSE stream; return message from last event: error data."""
    last_msg = None
    for event_type, data_json in _iter_sse_events(text):
        if event_type == "error" and "message" in data_json:
            last_msg = data_json.get("message", "")
    return last_msg


def parse_sse_model_context(text: str) -> dict | None:
    """Parse SSE stream; return data dict from last event: model_context."""
    last = None
    for event_type, data in _iter_sse_events(text):
        if event_type == "model_context":
            last = data
    return last


def is_non_retriable_query_error(error_msg: str) -> bool:
    """
    True if error indicates non-retriable failure (model not found, bad config).
    Retriable: overloaded (529), rate limits, throttling, 500 api_error — keep polling.
    """
    if not error_msg:
        return False
    msg_lower = error_msg.lower()
    # Retriable: overloaded, rate limits, throttling, 500 api_error
    if any(x in msg_lower for x in ("overloaded_error", "rate_limit", "throttl", "api_error", "internal server error")):
        return False
    # Model not found (404)
    if "not_found_error" in msg_lower or ("model:" in msg_lower and "404" in error_msg):
        return True
    # API/auth errors
    if "invalid_api_key" in msg_lower or ("authentication" in msg_lower and "failed" in msg_lower):
        return True
    # Explicit error type in embedded JSON
    if "'type': 'error'" in error_msg or '"type":"error"' in error_msg.replace(" ", ""):
        return True
    return False


def is_agent_disabled_by_config() -> bool:
    """True if USE_AGENT_QUERY is false in env (same source as deploy)."""
    val = (os.getenv("USE_AGENT_QUERY") or "true").lower()
    return val in ("false", "0", "no", "off", "")


def parse_sse_events(text: str, event_type: str) -> list[dict]:
    """Return data dicts for all SSE events of the given type."""
    return [
        data
        for et, data in _iter_sse_events(text)
        if et == event_type
    ]


def first_event_index(text: str, event_type: str) -> int | None:
    """Zero-based index of the nth event block matching event_type, or None."""
    idx = 0
    for et, _ in _iter_sse_events(text):
        if et == event_type:
            return idx
        idx += 1
    return None


def semantic_search_completes(text: str) -> list[dict]:
    """tool_call_complete payloads where tool is semantic_search."""
    return [
        d
        for d in parse_sse_tool_call_complete_events(text)
        if d.get("tool") == "semantic_search"
    ]


def is_semantic_hit(event: dict) -> bool:
    output = event.get("output") or {}
    return bool(output.get("success")) and (output.get("row_count") or 0) > 0


def assert_no_semantic_after_first_hit(events: list[dict]) -> None:
    """Raise AssertionError if any semantic_search complete follows a successful hit."""
    hits = [e for e in events if is_semantic_hit(e)]
    if not hits:
        return
    first_idx = events.index(hits[0])
    later = [e for e in events[first_idx + 1 :] if e.get("tool") == "semantic_search"]
    if later:
        raise AssertionError(f"semantic_search after first hit: {len(later)} extra event(s)")


def assert_event_order(text: str, expected_types: list[str]) -> None:
    """Assert SSE event types appear in order (extras between allowed)."""
    seen_idx = 0
    for event_type, _ in _iter_sse_events(text):
        if seen_idx < len(expected_types) and event_type == expected_types[seen_idx]:
            seen_idx += 1
    if seen_idx < len(expected_types):
        missing = expected_types[seen_idx:]
        raise AssertionError(f"SSE event order missing: {missing}")
