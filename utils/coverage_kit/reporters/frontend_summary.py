"""Read Vitest / Playwright raw coverage headline numbers."""

from __future__ import annotations

import json
from pathlib import Path


def read_vitest_summary(path: Path) -> dict[str, float | None]:
    """Parse Vitest ``json-summary`` / ``coverage-summary.json`` totals."""
    out: dict[str, float | None] = {
        "lines": None,
        "statements": None,
        "functions": None,
        "branches": None,
    }
    if not path.is_file():
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return out
    total = data.get("total") if isinstance(data, dict) else None
    if not isinstance(total, dict):
        return out
    for key in out:
        block = total.get(key)
        if isinstance(block, dict) and "pct" in block:
            try:
                out[key] = float(block["pct"])
            except (TypeError, ValueError):
                pass
    return out


def playwright_raw_file_count(
    raw_dir: Path,
    *,
    prefix: str | None = None,
    exclude_prefix: str | None = None,
) -> int:
    if not raw_dir.is_dir():
        return 0
    count = 0
    for p in raw_dir.glob("*.json"):
        if prefix and not p.name.startswith(prefix):
            continue
        if exclude_prefix and p.name.startswith(exclude_prefix):
            continue
        count += 1
    return count
