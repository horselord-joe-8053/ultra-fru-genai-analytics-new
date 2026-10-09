"""Resolve frontend coverage artifact directory (Vitest + Playwright raw JSON)."""

from __future__ import annotations

import os
from pathlib import Path

from .cover_layout import DEFAULT_FRONTEND_COVERAGE_REL


def apply_frontend_coverage_env(env: dict[str, str], repo_root: Path) -> dict[str, str]:
    """Return ``env`` copy with canonical ``FRONTEND_COVERAGE_DIR`` for subprocess collectors."""
    out = dict(env)
    raw = out.get("FRONTEND_COVERAGE_DIR", "").strip() or out.get("COV_FRONTEND_COVERAGE_DIR", "").strip()
    if raw:
        p = Path(raw)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                rel = p.as_posix()
        else:
            rel = raw
        out["FRONTEND_COVERAGE_DIR"] = rel.replace("\\", "/").strip().rstrip("/")
    else:
        out["FRONTEND_COVERAGE_DIR"] = DEFAULT_FRONTEND_COVERAGE_REL
    out.pop("COV_FRONTEND_COVERAGE_DIR", None)
    return out


def _env_frontend_coverage_rel() -> str:
    raw = os.environ.get("FRONTEND_COVERAGE_DIR", "").strip()
    if raw:
        return raw.replace("\\", "/").strip().rstrip("/")
    raw = os.environ.get("COV_FRONTEND_COVERAGE_DIR", "").strip()
    if raw:
        return raw.replace("\\", "/").strip().rstrip("/")
    return DEFAULT_FRONTEND_COVERAGE_REL


def frontend_package_root(repo_root: Path) -> Path:
    """``apps/web`` from monorepo root."""
    return (repo_root / "apps" / "web").resolve()


def resolve_frontend_coverage_dir(repo_root: Path) -> Path:
    """Canonical frontend coverage tree (Vitest HTML, landing, ``playwright-raw/``).

    **Env:** ``FRONTEND_COVERAGE_DIR`` or portable ``COV_FRONTEND_COVERAGE_DIR``.
    Relative values are under the **repository root** (default ``tests/coverage/artifacts/frontend``).
    Absolute paths are used as-is.
    """
    rel = _env_frontend_coverage_rel()
    p = Path(rel)
    if p.is_absolute():
        return p.resolve()
    return (repo_root / p).resolve()


def playwright_raw_dir(repo_root: Path) -> Path:
    return resolve_frontend_coverage_dir(repo_root) / "playwright-raw"
