"""Backend ``coverage.py`` combine, report, and HTML."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .config import CoverageKitConfig
from .cover_layout import (
    MERGED_COVERAGE_BASENAME,
    MOCKED_BACKEND_COVERAGE_BASENAME,
    PHASE01_BASENAME,
    PHASE02_BASENAME,
    delete_data_files_after_merge,
)


def mocked_backend_data_files(config: CoverageKitConfig) -> list[Path]:
    """API coverage from instrumented mocked Playwright (phase 4 ``--cov``)."""
    p = config.backend_data_dir / MOCKED_BACKEND_COVERAGE_BASENAME
    return [p] if p.is_file() else []


def e2e_backend_data_files(config: CoverageKitConfig) -> list[Path]:
    """Per-phase API coverage from instrumented ``e2e-test`` stacks (phases 5–13)."""
    data = config.backend_data_dir
    return sorted(
        p
        for p in data.glob(".coverage.e2e.*")
        if p.is_file() and p.name != MOCKED_BACKEND_COVERAGE_BASENAME
    )


def backend_data_globs(config: CoverageKitConfig) -> list[Path]:
    """Phase-tagged and E2E backend data files to combine."""
    data = config.backend_data_dir
    patterns = [PHASE01_BASENAME, PHASE02_BASENAME, MERGED_COVERAGE_BASENAME]
    out: list[Path] = []
    for name in patterns:
        p = data / name
        if p.is_file():
            out.append(p)
    out.extend(e2e_backend_data_files(config))
    return out


def _coverage_argv(config: CoverageKitConfig, *tail: str) -> list[str]:
    return [
        "uv",
        "run",
        "--project",
        str(config.api_project_dir),
        "--group",
        "dev",
        "coverage",
        *tail,
    ]


def combine_backend_data(config: CoverageKitConfig) -> list[str]:
    """Run ``coverage combine`` on discovered data files; return basenames combined."""
    data = config.backend_data_dir
    data.mkdir(parents=True, exist_ok=True)
    files = backend_data_globs(config)
    if not files:
        return []
    merged = data / MERGED_COVERAGE_BASENAME
    if len(files) == 1 and files[0].name == MERGED_COVERAGE_BASENAME:
        return [MERGED_COVERAGE_BASENAME]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"apps/api{os.pathsep}{config.repo_root}"
    env["COVERAGE_FILE"] = str(merged)
    argv: list[str] = ["combine"]
    if not delete_data_files_after_merge():
        argv.append("--keep")
    argv.extend(str(f) for f in files)
    proc = subprocess.run(
        _coverage_argv(config, *argv),
        cwd=config.repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"coverage combine failed ({proc.returncode}): {proc.stderr or proc.stdout}"
        )
    return [f.name for f in files]


def _coverage_env(config: CoverageKitConfig, *, coverage_file: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"apps/api{os.pathsep}{config.repo_root}"
    if coverage_file is not None:
        env["COVERAGE_FILE"] = str(coverage_file)
    return env


def _run_coverage_report_rcfile(
    config: CoverageKitConfig,
    *,
    rcfile: Path,
    fail_under: bool,
    coverage_file: Path | None,
    cwd: Path,
) -> tuple[int, str]:
    tail = ["report", "--rcfile", str(rcfile)]
    if fail_under:
        tail.append("--fail-under")
    proc = subprocess.run(
        _coverage_argv(config, *tail),
        cwd=cwd,
        env=_coverage_env(config, coverage_file=coverage_file),
        capture_output=True,
        text=True,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, text


def run_coverage_report(
    config: CoverageKitConfig,
    *,
    fail_under: bool,
    coverage_file: Path | None = None,
    cwd_api: bool = False,
) -> tuple[int, str]:
    """Text report; optional ``--fail-under`` gate from ``tests/coverage/.coveragerc``."""
    merged = config.backend_data_dir / MERGED_COVERAGE_BASENAME
    cov_file = coverage_file if coverage_file is not None else (
        merged if merged.is_file() else None
    )
    return _run_coverage_report_rcfile(
        config,
        rcfile=config.coveragerc,
        fail_under=fail_under,
        coverage_file=cov_file,
        cwd=config.api_project_dir if cwd_api else config.repo_root,
    )


def lines_pct_from_coverage_data_files(
    config: CoverageKitConfig,
    data_files: list[Path],
) -> float | None:
    """Combine the given data files in a temp DB and return TOTAL line % (no clobber)."""
    import tempfile

    if not data_files:
        return None
    if len(data_files) == 1 and data_files[0].is_file():
        e2e_rc = config.api_project_dir / ".coveragerc.e2e"
        rcfile = e2e_rc.resolve() if e2e_rc.is_file() else config.coveragerc
        _, report_text = _run_coverage_report_rcfile(
            config,
            rcfile=rcfile,
            fail_under=False,
            coverage_file=data_files[0].resolve(),
            cwd=config.api_project_dir,
        )
        lines_pct, _, _ = parse_backend_totals(report_text)
        return lines_pct
    with tempfile.TemporaryDirectory(prefix="covkit-pw-be-") as tmp:
        combined = Path(tmp) / MERGED_COVERAGE_BASENAME
        env = _coverage_env(config, coverage_file=combined)
        argv = _coverage_argv(
            config,
            "combine",
            "--keep",
            *[str(f.resolve()) for f in data_files],
        )
        proc = subprocess.run(
            argv,
            cwd=config.repo_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not combined.is_file():
            return None
        _, report_text = run_coverage_report(
            config, fail_under=False, coverage_file=combined
        )
        lines_pct, _, _ = parse_backend_totals(report_text)
        return lines_pct


def run_coverage_html(config: CoverageKitConfig) -> int:
    config.backend_html_dir.mkdir(parents=True, exist_ok=True)
    merged = config.backend_data_dir / MERGED_COVERAGE_BASENAME
    env = _coverage_env(
        config,
        coverage_file=merged if merged.is_file() else None,
    )
    proc = subprocess.run(
        _coverage_argv(
            config,
            "html",
            "--rcfile",
            str(config.coveragerc),
            "-d",
            str(config.backend_html_dir),
        ),
        cwd=config.repo_root,
        env=env,
    )
    return proc.returncode


def parse_backend_totals(report_text: str) -> tuple[float | None, float | None, float | None]:
    """Parse ``TOTAL`` line from ``coverage report`` text."""
    lines_pct: float | None = None
    branches_pct: float | None = None
    fail_under: float | None = None
    for line in report_text.splitlines():
        if line.strip().startswith("TOTAL"):
            parts = line.split()
            for part in parts:
                if part.endswith("%"):
                    try:
                        val = float(part.rstrip("%"))
                    except ValueError:
                        continue
                    if lines_pct is None:
                        lines_pct = val
                    else:
                        branches_pct = val
        m = re.search(r"fail-under\s*=\s*(\d+(?:\.\d+)?)", line, re.I)
        if m:
            fail_under = float(m.group(1))
    if fail_under is None:
        fail_under = 78.0
    return lines_pct, branches_pct, fail_under
