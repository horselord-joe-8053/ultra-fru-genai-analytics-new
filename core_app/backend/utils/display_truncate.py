"""
Display truncation for Execution Log SSE payloads (SQL preview length).

Applicable environment: [local] [aws {ecs | eks}] [azure {aci | aks}] [gcp {cloud-run | gke}]
"""
import os

_DEFAULT_MAX = 150
_CLAMP_MAX = 500
_ENV_KEY = "EXEC_LOG_SQL_PREVIEW_MAX_CHARS"

# Substrings that indicate the LLM passed a placeholder instead of real SQL.
_SQL_PLACEHOLDER_MARKERS = (
    "(the sql",
    "the sql query",
    "[the sql",
    "[will use",
    "<will use",
    "from generate_sql",
)


def get_exec_log_sql_preview_max_chars() -> int:
    """Read EXEC_LOG_SQL_PREVIEW_MAX_CHARS; default 150; clamp to 0..500."""
    raw = os.environ.get(_ENV_KEY, "").strip()
    if not raw:
        return _DEFAULT_MAX
    try:
        n = int(raw)
    except ValueError:
        return _DEFAULT_MAX
    if n <= 0:
        return 0
    return min(n, _CLAMP_MAX)


def truncate_for_exec_log(text: str, max_chars: int | None = None) -> str:
    """Truncate with ellipsis for display. max_chars <= 0 means no truncation."""
    if max_chars is None:
        max_chars = get_exec_log_sql_preview_max_chars()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def is_sql_placeholder(s: str) -> bool:
    """True when the string looks like an LLM placeholder, not executable SQL."""
    if not s or not isinstance(s, str):
        return True
    lower = s.strip().lower()
    if not lower:
        return True
    return any(marker in lower for marker in _SQL_PLACEHOLDER_MARKERS)
