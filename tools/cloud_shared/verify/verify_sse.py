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
