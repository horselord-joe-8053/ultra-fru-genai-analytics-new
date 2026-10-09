"""
Normalize LLM-generated SQL for PostgreSQL execution.

Rewrites known MySQL-only constructs before execute_sql. Extend the table below
when new dialect mistakes appear in logs — not a full MySQL translator.

Applicable environment: [local] [aws {ecs | eks}] [azure {aci | aks}] [gcp {cloud-run | gke}]
"""
import re

# SUBSTRING_INDEX(col, delim, n) -> SPLIT_PART(col, delim, n)
# Delim may be a quoted string (e.g. ',') so [^,]+ alone is insufficient.
_SUBSTRING_INDEX_RE = re.compile(
    r"SUBSTRING_INDEX\s*\(\s*([^,]+?)\s*,\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[^,]+?)\s*,\s*(\d+)\s*\)",
    re.IGNORECASE,
)


def normalize_postgresql_sql(sql: str) -> str:
    """Apply dialect rewrites so generated SQL runs on PostgreSQL."""
    if not sql:
        return sql
    return _SUBSTRING_INDEX_RE.sub(r"SPLIT_PART(\1, \2, \3)", sql)
