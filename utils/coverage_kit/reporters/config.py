"""Dataclasses for coverage finalize (project adapter fills these)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CoverageKitConfig:
    """Paths and tool locations for one repository."""

    repo_root: Path
    coveragerc: Path
    backend_data_dir: Path
    backend_html_dir: Path
    frontend_root: Path
    frontend_coverage_dir: Path
    frontend_landing_index: Path
    playwright_raw_dir: Path
    vitest_summary_json: Path
    api_project_dir: Path
    dashboard_root: Path
    dashboard_htdocs_dir: Path
    session_marker_path: Path


@dataclass(frozen=True)
class CoveragePhaseResult:
    """Optional metadata from the orchestrator (e.g. resall)."""

    label: str
    ran: bool = True
    notes: str = ""


@dataclass
class CoverageFinalizeResult:
    """Outcome of ``finalize_coverage`` for exit-code aggregation."""

    exit_code: int = 0
    partial: bool = False
    partial_reason: str = ""
    backend_lines_pct: float | None = None
    backend_fail_under: float | None = None
    vitest_lines_pct: float | None = None
    vitest_thresholds_ok: bool | None = None
    combined_data_files: list[str] = field(default_factory=list)
    mocked_playwright_dump_count: int = 0
    e2e_playwright_dump_count: int = 0
    summary_lines: list[str] = field(default_factory=list)
    dashboard_url: str | None = None
