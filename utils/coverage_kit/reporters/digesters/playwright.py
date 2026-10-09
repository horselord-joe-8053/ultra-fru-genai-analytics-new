"""Digest Playwright Istanbul raw JSON dumps (mocked + E2E)."""

from __future__ import annotations

import json
from pathlib import Path

from ..backend import (
    e2e_backend_data_files,
    lines_pct_from_coverage_data_files,
    mocked_backend_data_files,
)
from ..config import CoverageKitConfig
from ..model import SurfaceSnapshot
from .base import CoverageDigester


def merge_istanbul_files(paths: list[Path]) -> dict[str, object]:
    """Merge Istanbul ``__coverage__`` objects from multiple dump files."""
    merged: dict[str, object] = {}
    for path in paths:
        try:
            chunk = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(chunk, dict):
            merged.update(chunk)
    return merged


def istanbul_statement_pct(data: dict[str, object]) -> float | None:
    """Approximate line/statement coverage % from Istanbul file entries."""
    total = 0
    covered = 0
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        sm = entry.get("statementMap")
        hits = entry.get("s")
        if not isinstance(sm, dict) or not isinstance(hits, dict):
            continue
        for stmt_id in sm:
            total += 1
            key = str(stmt_id)
            try:
                hit = int(hits.get(key, 0))
            except (TypeError, ValueError):
                hit = 0
            if hit > 0:
                covered += 1
    if total == 0:
        return None
    return round(100.0 * covered / total, 2)


def _digest_playwright_family(
    raw_dir: Path,
    config: CoverageKitConfig,
    *,
    surface_id: str,
    label: str,
    name_prefix: str | None,
    exclude_prefix: str | None,
    backend_data_files: list[Path] | None = None,
) -> SurfaceSnapshot | None:
    if not raw_dir.is_dir():
        return None
    paths: list[Path] = []
    for path in sorted(raw_dir.glob("*.json")):
        if name_prefix and not path.name.startswith(name_prefix):
            continue
        if exclude_prefix and path.name.startswith(exclude_prefix):
            continue
        paths.append(path)
    if not paths:
        return None
    merged = merge_istanbul_files(paths)
    frontend_lines = istanbul_statement_pct(merged)
    backend_lines: float | None = None
    notes = f"{len(paths)} raw dump(s) under playwright-raw/"
    if backend_data_files:
        backend_lines = lines_pct_from_coverage_data_files(config, backend_data_files)
        if backend_lines is not None:
            notes += f"; backend {len(backend_data_files)} .coverage.e2e.* file(s)"
    elif surface_id == "playwright_mocked":
        notes += "; backend n/a (mocked specs route API in the browser)"
    return SurfaceSnapshot(
        surface_id=surface_id,
        label=label,
        lines_pct=frontend_lines,
        backend_lines_pct=backend_lines,
        file_count=len(merged) if merged else 0,
        raw_dump_count=len(paths),
        partial=frontend_lines is None and bool(merged),
        notes=notes,
    )


class PlaywrightRawDigester(CoverageDigester):
    """Produces separate mocked and E2E surfaces when dumps exist."""

    def digest(self, config: CoverageKitConfig) -> list[SurfaceSnapshot]:
        raw = config.playwright_raw_dir
        out: list[SurfaceSnapshot] = []
        mocked = _digest_playwright_family(
            raw,
            config,
            surface_id="playwright_mocked",
            label="Playwright mocked (phase 4)",
            name_prefix=None,
            exclude_prefix="e2e-",
            backend_data_files=mocked_backend_data_files(config),
        )
        if mocked is not None:
            out.append(mocked)
        e2e_backend = e2e_backend_data_files(config)
        e2e = _digest_playwright_family(
            raw,
            config,
            surface_id="playwright_e2e",
            label="Playwright E2E (phases 5–13)",
            name_prefix="e2e-",
            exclude_prefix=None,
            backend_data_files=e2e_backend,
        )
        if e2e is not None:
            out.append(e2e)
        return out
