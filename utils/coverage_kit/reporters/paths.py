"""Default artifact paths for this repo layout (adapter may override)."""

from __future__ import annotations

from pathlib import Path

from .config import CoverageKitConfig
from .cover_layout import (
    backend_data_dir,
    backend_html_dir,
    coveragerc_path,
    dashboard_root,
)
from .frontend_paths import frontend_package_root, resolve_frontend_coverage_dir


def default_config(repo_root: Path) -> CoverageKitConfig:
    web = frontend_package_root(repo_root)
    cov_dir = resolve_frontend_coverage_dir(repo_root)
    dash = dashboard_root(repo_root)
    return CoverageKitConfig(
        repo_root=repo_root,
        coveragerc=coveragerc_path(repo_root),
        backend_data_dir=backend_data_dir(repo_root),
        backend_html_dir=backend_html_dir(repo_root),
        frontend_root=web,
        frontend_coverage_dir=cov_dir,
        frontend_landing_index=cov_dir / "index.html",
        playwright_raw_dir=cov_dir / "playwright-raw",
        vitest_summary_json=cov_dir / "coverage-summary.json",
        api_project_dir=repo_root / "apps" / "api",
        dashboard_root=dash,
        dashboard_htdocs_dir=dash / "htdocs",
        session_marker_path=dash / ".resall-cov-session.json",
    )
