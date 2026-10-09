"""
Human-readable logging helpers for embedding sync (bootstrap / admin / CLI).
"""
from __future__ import annotations

from backend.services.embedding_sync_core import SyncResult

_PROGRESS_INTERVAL = 25


def progress_interval() -> int:
    return _PROGRESS_INTERVAL


def format_sync_result_summary(result: SyncResult) -> str:
    """One-line summary for operators."""
    parts = [
        f"embedded={result.embedded}",
        f"skipped={result.skipped}",
        f"failed={result.failed}",
    ]
    for name, counts in sorted(result.per_profile.items()):
        parts.append(
            f"{name}(+{counts.get('embedded', 0)}/skip{counts.get('skipped', 0)}/fail{counts.get('failed', 0)})"
        )
    return " ".join(parts)


def format_sync_result_detail(result: SyncResult) -> list[str]:
    """Multi-line detail for errors/warnings (not one lumped dict)."""
    lines: list[str] = [format_sync_result_summary(result)]
    for name, counts in sorted(result.per_profile.items()):
        lines.append(
            f"  profile {name}: embedded={counts.get('embedded', 0)} "
            f"skipped={counts.get('skipped', 0)} failed={counts.get('failed', 0)}"
        )
    for w in result.warnings:
        lines.append(f"  warning: {w}")
    for err in result.errors[:20]:
        lines.append(f"  error: {err}")
    if len(result.errors) > 20:
        lines.append(f"  ... and {len(result.errors) - 20} more errors")
    return lines
