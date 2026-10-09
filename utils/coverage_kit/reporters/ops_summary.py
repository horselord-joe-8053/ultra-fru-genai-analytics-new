"""Build the fixed-order ``[coverage] summary`` block for ops logs."""

from __future__ import annotations

from pathlib import Path

from .config import CoverageFinalizeResult


def build_coverage_summary_lines(
    result: CoverageFinalizeResult,
    *,
    backend_html: Path,
    frontend_landing: Path,
    e2e_instrumented: bool,
    dashboard_url: str | None = None,
) -> list[str]:
    lines = ["[coverage] summary"]
    bl = result.backend_lines_pct
    fu = result.backend_fail_under
    if bl is not None and fu is not None:
        gate = "pass" if result.exit_code == 0 and not result.partial else "see exit code"
        lines.append(f"Backend: {bl:.1f}% lines — fail_under {fu:.0f}% — {gate}")
    else:
        lines.append("Backend: n/a (no combined data)")
    lines.append(f"Backend HTML: {backend_html}")
    vt = result.vitest_lines_pct
    if vt is not None:
        th = "pass" if result.vitest_thresholds_ok else "FAIL"
        lines.append(f"Frontend Vitest: {vt:.1f}% lines — thresholds {th}")
    else:
        lines.append("Frontend Vitest: n/a (missing coverage-summary.json)")
    lines.append(
        f"Frontend mocked Playwright: {result.mocked_playwright_dump_count} raw dump(s) in playwright-raw/"
    )
    if e2e_instrumented:
        lines.append(f"Frontend E2E Playwright: {result.e2e_playwright_dump_count} e2e-* dump(s)")
    else:
        lines.append(
            "Frontend E2E Playwright: not run — set RESALL_COV_E2E_INSTRUMENT=1 to include phases 5–13"
        )
    lines.append(f"Frontend combined: see landing page — {frontend_landing}")
    if e2e_instrumented:
        lines.append(f"E2E phases 5–13: instrumented ({result.e2e_playwright_dump_count} playwright-raw dumps)")
    else:
        lines.append("E2E phases 5–13: not included (RESALL_COV_E2E_INSTRUMENT=0)")
    if result.combined_data_files:
        lines.append(f"Backend data files combined: {', '.join(result.combined_data_files)}")
    status = "partial — " + result.partial_reason if result.partial else "complete"
    lines.append(f"Status: {status}")
    if dashboard_url:
        lines.append(f"Coverage dashboard: {dashboard_url} (also /code-coverage/)")
        lines.append(
            "Dashboard session: tests/coverage/artifacts/backend/dashboard/.resall-cov-session.json"
        )
    return lines
