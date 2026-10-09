"""Orchestrate backend + frontend finalize after collectors run."""

from __future__ import annotations

from .backend import (
    combine_backend_data,
    parse_backend_totals,
    run_coverage_html,
    run_coverage_report,
)
from .config import CoverageFinalizeResult, CoverageKitConfig
from .env import CoverageEnv
from .frontend_landing import build_frontend_landing_index
from .frontend_summary import playwright_raw_file_count, read_vitest_summary


def finalize_coverage(
    config: CoverageKitConfig,
    env: CoverageEnv,
    *,
    ritual_rc: int,
    phases_completed: int,
    total_phases: int,
    e2e_instrumented: bool,
    main_phase_count: int | None = None,
) -> CoverageFinalizeResult:
    """Combine data, emit HTML, build summary lines. **O5:** runs even when ``ritual_rc != 0``."""
    result = CoverageFinalizeResult()
    partial_reasons: list[str] = []

    if phases_completed < 4:
        partial_reasons.append(f"only {phases_completed}/4 baseline phases completed")
    if ritual_rc != 0:
        partial_reasons.append(f"ritual exit {ritual_rc}")
    if phases_completed < total_phases:
        post_cov_only_gap = (
            main_phase_count is not None
            and phases_completed >= main_phase_count
            and (total_phases - phases_completed) <= (total_phases - main_phase_count)
        )
        if not post_cov_only_gap:
            partial_reasons.append(f"{phases_completed}/{total_phases} resall phases finished")

    try:
        result.combined_data_files = combine_backend_data(config)
    except RuntimeError as exc:
        partial_reasons.append(f"backend combine: {exc}")
        result.combined_data_files = []

    report_rc, report_text = run_coverage_report(config, fail_under=False)
    lines_pct, _branches, fail_under = parse_backend_totals(report_text)
    result.backend_lines_pct = lines_pct
    result.backend_fail_under = fail_under

    gate_rc = 0
    if result.combined_data_files and lines_pct is not None and fail_under is not None:
        if lines_pct < fail_under:
            gate_rc = 1
            partial_reasons.append(
                f"backend lines {lines_pct:.1f}% below fail_under {fail_under:.0f}%"
            )

    if env.emit_html and result.combined_data_files:
        html_rc = run_coverage_html(config)
        if html_rc != 0:
            partial_reasons.append(f"coverage html exit {html_rc}")

    vitest = read_vitest_summary(config.vitest_summary_json)
    result.vitest_lines_pct = vitest.get("lines")
    result.vitest_thresholds_ok = _vitest_thresholds_ok(vitest)

    result.mocked_playwright_dump_count = playwright_raw_file_count(
        config.playwright_raw_dir, exclude_prefix="e2e-"
    )
    result.e2e_playwright_dump_count = (
        playwright_raw_file_count(config.playwright_raw_dir, prefix="e2e-")
        if e2e_instrumented
        else 0
    )

    build_frontend_landing_index(
        landing_path=config.frontend_landing_index,
        vitest_summary_path=config.vitest_summary_json,
        mocked_raw_dir=config.playwright_raw_dir,
        e2e_raw_dir=config.playwright_raw_dir,
        e2e_instrumented=e2e_instrumented,
    )

    result.partial = bool(partial_reasons)
    result.partial_reason = "; ".join(partial_reasons) if partial_reasons else ""

    exit_codes = [ritual_rc]
    if gate_rc != 0:
        exit_codes.append(gate_rc)
    if result.vitest_thresholds_ok is False:
        exit_codes.append(1)
    result.exit_code = max(exit_codes) if exit_codes else 0

    # Always build dashboard assets at finalize time.
    # Serving lifecycle is owned by ops/local/run_cov_dashboard.py (one-shot verify
    # and run_all persistent service), not by env gating in the reporter layer.
    dashboard_url: str | None = None
    from .dashboard_build import build_dashboard_htdocs
    from .dashboard_serve import dashboard_base_url, write_session_marker

    build_dashboard_htdocs(config, result, e2e_instrumented=e2e_instrumented)
    if (config.dashboard_htdocs_dir / "index.html").is_file():
        dashboard_url = dashboard_base_url(
            bind=env.dashboard_bind, port=env.dashboard_port
        )
        write_session_marker(
            config.session_marker_path,
            bind=env.dashboard_bind,
            port=env.dashboard_port,
            dashboard_url=dashboard_url,
        )
    result.dashboard_url = dashboard_url

    from .ops_summary import build_coverage_summary_lines

    result.summary_lines = build_coverage_summary_lines(
        result,
        backend_html=config.backend_html_dir / "index.html",
        frontend_landing=config.frontend_landing_index,
        e2e_instrumented=e2e_instrumented,
        dashboard_url=dashboard_url,
    )
    return result


def _vitest_thresholds_ok(vitest: dict[str, float | None]) -> bool | None:
    """Align with ``vite.config.ts`` thresholds when summary present."""
    lines = vitest.get("lines")
    branches = vitest.get("branches")
    functions = vitest.get("functions")
    if lines is None:
        return None
    if lines < 48:
        return False
    if branches is not None and branches < 70:
        return False
    if functions is not None and functions < 47:
        return False
    return True
