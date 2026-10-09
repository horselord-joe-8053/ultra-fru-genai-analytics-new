"""Canonical ``tests/coverage/`` layout for coverage config, data, and reports."""

from __future__ import annotations

import os
from pathlib import Path

# Relative to repository root (``coverage`` collectors use ``cwd=repo_root``).
# Keep DEFAULT_FRONTEND_COVERAGE_REL in sync with utils/coverage_kit/collectors/paths.ts.
COVER_ROOT_REL = "tests/coverage"
DEFAULT_FRONTEND_COVERAGE_REL = f"{COVER_ROOT_REL}/artifacts/frontend"
BACKEND_DATA_REL = f"{COVER_ROOT_REL}/artifacts/backend/data"
BACKEND_HTML_REL = f"{COVER_ROOT_REL}/artifacts/backend/api-htmlcov"
DASHBOARD_REL = f"{COVER_ROOT_REL}/artifacts/backend/dashboard"

MOCKED_BACKEND_COVERAGE_BASENAME = ".coverage.e2e.mocked"
PHASE01_BASENAME = ".coverage.phase01"
PHASE02_BASENAME = ".coverage.phase02"
MERGED_COVERAGE_BASENAME = ".coverage"


def cover_root(repo_root: Path) -> Path:
    return (repo_root / COVER_ROOT_REL).resolve()


def coveragerc_path(repo_root: Path) -> Path:
    return cover_root(repo_root) / ".coveragerc"


def backend_data_dir(repo_root: Path) -> Path:
    return (repo_root / BACKEND_DATA_REL).resolve()


def backend_data_file(repo_root: Path, basename: str) -> Path:
    """Per-phase or merged ``coverage.py`` SQLite file under ``artifacts/backend/data/``."""
    return backend_data_dir(repo_root) / basename


def backend_html_dir(repo_root: Path) -> Path:
    return (repo_root / BACKEND_HTML_REL).resolve()


def dashboard_root(repo_root: Path) -> Path:
    return (repo_root / DASHBOARD_REL).resolve()


def delete_data_files_after_merge() -> bool:
    """When true, ``coverage combine`` may remove per-phase inputs (default: keep)."""
    for key in ("COV_DATA_DELETE_AFTER_MERGED", "RESALL_COV_DATA_DELETE_AFTER_MERGED"):
        raw = os.environ.get(key, "").strip().lower()
        if raw in ("1", "true", "yes", "on"):
            return True
    return False
