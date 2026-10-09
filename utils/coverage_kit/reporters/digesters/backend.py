"""Digest coverage.py HTML report into a backend surface snapshot."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import CoverageKitConfig
from ..model import SurfaceSnapshot
from .base import CoverageDigester

# coverage.py 7 HTML: total row line column uses data-ratio="missed covered total".
_TOTAL_LINE_RATIO = re.compile(
    r'<tr class="total">.*?'
    r'data-ratio="(\d+)\s+(\d+)\s+(\d+)"',
    re.DOTALL | re.IGNORECASE,
)


def parse_backend_html_index(html: str) -> dict[str, float | None]:
    """Extract line % from coverage.py ``index.html`` total row."""
    out: dict[str, float | None] = {"lines": None}
    match = _TOTAL_LINE_RATIO.search(html)
    if not match:
        return out
    missed_s, covered_s, total_s = match.groups()
    try:
        missed = int(missed_s)
        covered = int(covered_s)
        total = int(total_s)
    except ValueError:
        return out
    if total <= 0:
        return out
    out["lines"] = round(100.0 * covered / total, 2)
    return out


class BackendCoverageDigester(CoverageDigester):
    def digest(self, config: CoverageKitConfig) -> list[SurfaceSnapshot]:
        index = config.backend_html_dir / "index.html"
        if not index.is_file():
            return []
        try:
            html = index.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        metrics = parse_backend_html_index(html)
        lines = metrics.get("lines")
        return [
            SurfaceSnapshot(
                surface_id="backend",
                label="Backend (combined unittest + openapi)",
                lines_pct=lines,
                detail_href="reports/backend/index.html",
                partial=lines is None,
                notes="Parsed from coverage.py HTML" if lines is not None else "HTML present; total row not parsed",
            )
        ]
