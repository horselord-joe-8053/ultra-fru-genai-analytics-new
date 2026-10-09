"""Digest Vitest ``coverage-summary.json`` into a frontend unit-test surface."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import CoverageKitConfig
from ..frontend_summary import read_vitest_summary
from ..model import FileCoverage, SurfaceSnapshot
from .base import CoverageDigester

_TOP_FILES_LIMIT = 8


def _top_files_from_summary(path: Path, *, limit: int = _TOP_FILES_LIMIT) -> tuple[FileCoverage, ...]:
    if not path.is_file():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()
    if not isinstance(data, dict):
        return ()
    rows: list[FileCoverage] = []
    for key, block in data.items():
        if key == "total" or not isinstance(block, dict):
            continue
        lines = block.get("lines")
        pct: float | None = None
        if isinstance(lines, dict) and "pct" in lines:
            try:
                pct = float(lines["pct"])
            except (TypeError, ValueError):
                pct = None
        rows.append(FileCoverage(path=str(key), lines_pct=pct))
    rows.sort(key=lambda r: (r.lines_pct if r.lines_pct is not None else -1.0))
    return tuple(rows[:limit])


class VitestCoverageDigester(CoverageDigester):
    def digest(self, config: CoverageKitConfig) -> list[SurfaceSnapshot]:
        summary_path = config.vitest_summary_json
        totals = read_vitest_summary(summary_path)
        if totals.get("lines") is None and not summary_path.is_file():
            return []
        top = _top_files_from_summary(summary_path)
        return [
            SurfaceSnapshot(
                surface_id="vitest",
                label="Frontend Vitest",
                lines_pct=totals.get("lines"),
                statements_pct=totals.get("statements"),
                functions_pct=totals.get("functions"),
                branches_pct=totals.get("branches"),
                file_count=len(top) if top else None,
                detail_href="reports/frontend/vitest-html/index.html"
                if (config.frontend_coverage_dir / "vitest-html" / "index.html").is_file()
                else "reports/frontend/index.html",
                partial=totals.get("lines") is None,
                top_files=top,
            )
        ]
