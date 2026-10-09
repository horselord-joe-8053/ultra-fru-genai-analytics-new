"""
Display helpers for Execution Log SSE payloads (SQL preview, quoting, token usage).

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


def unwrap_sql_literal(s: str) -> str:
    """Strip one layer of surrounding quotes from LLM copy-paste (display or execution)."""
    t = s.strip()
    if len(t) >= 2 and t[0] == "'" and t[-1] == "'":
        return t[1:-1].replace("''", "'")
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        return t[1:-1]
    return t


def is_executable_select_sql(s: str) -> bool:
    """True when unwrap + placeholder check yields a SELECT (matches SQLTool gate)."""
    if not s or not isinstance(s, str):
        return False
    inner = unwrap_sql_literal(s.strip())
    if is_sql_placeholder(inner):
        return False
    return inner.upper().startswith("SELECT")


def resolve_execute_sql(
    raw: str | None,
    fallback_sql: str | None,
) -> str | None:
    """
    Pick SQL to run or show: unwrap quoted literals; backfill from generate_sql when invalid.

    Used by execute_sql normalization and Execution Log display so both paths agree.
    """
    if raw and is_executable_select_sql(raw):
        return unwrap_sql_literal(raw.strip())
    if fallback_sql and is_executable_select_sql(fallback_sql):
        return unwrap_sql_literal(fallback_sql.strip())
    return None


def quote_for_exec_log(sql: str, max_chars: int | None = None) -> str:
    """Truncate (if needed), escape embedded quotes, wrap in single quotes for display."""
    preview = truncate_for_exec_log(sql, max_chars)
    escaped = preview.replace("'", "''")
    return f"'{escaped}'"


def normalize_token_usage(raw: dict | None) -> dict:
    """Normalize LLM token dict to {input_tokens, output_tokens, total_tokens}."""
    if not raw:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if any(k in raw for k in ("input_tokens", "output_tokens", "total_tokens")):
        return {
            "input_tokens": int(raw.get("input_tokens") or 0),
            "output_tokens": int(raw.get("output_tokens") or 0),
            "total_tokens": int(raw.get("total_tokens") or 0),
        }
    return {
        "input_tokens": int(raw.get("input") or 0),
        "output_tokens": int(raw.get("output") or 0),
        "total_tokens": int(raw.get("total") or 0),
    }


def add_token_usage(acc: dict, raw: dict | None) -> dict:
    """Add normalized usage into running accumulator."""
    normalized = normalize_token_usage(raw)
    return {
        "input_tokens": acc.get("input_tokens", 0) + normalized["input_tokens"],
        "output_tokens": acc.get("output_tokens", 0) + normalized["output_tokens"],
        "total_tokens": acc.get("total_tokens", 0) + normalized["total_tokens"],
    }
