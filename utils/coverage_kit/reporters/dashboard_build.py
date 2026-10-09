"""Build stitched coverage dashboard static site (Stage 1 — iframe shell)."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .config import CoverageFinalizeResult, CoverageKitConfig
from .digesters import build_unified_coverage_model
from .model import SurfaceSnapshot, UnifiedCoverageModel


def _link_tree(src: Path, dest: Path) -> None:
    """Symlink directory into dashboard htdocs; fall back to copy if link fails."""
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.symlink_to(src.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(src, dest, symlinks=True, dirs_exist_ok=True)


def build_dashboard_htdocs(
    config: CoverageKitConfig,
    result: CoverageFinalizeResult,
    *,
    e2e_instrumented: bool,
) -> Path:
    """Create ``htdocs/`` with left-nav shell and symlinked report trees."""
    htdocs = config.dashboard_htdocs_dir
    if htdocs.exists():
        shutil.rmtree(htdocs)
    htdocs.mkdir(parents=True)
    reports = htdocs / "reports"
    reports.mkdir()

    backend_src = config.backend_html_dir
    if backend_src.is_dir():
        _link_tree(backend_src, reports / "backend")

    frontend_cov = config.frontend_coverage_dir
    if frontend_cov.is_dir():
        _link_tree(frontend_cov, reports / "frontend")

    vitest_html = frontend_cov / "vitest-html"
    model = build_unified_coverage_model(
        config,
        finalize=result,
        e2e_instrumented=e2e_instrumented,
    )
    mocked_n = result.mocked_playwright_dump_count
    e2e_n = result.e2e_playwright_dump_count if e2e_instrumented else 0

    summary_html = _summary_panel(model)
    index_html = _shell_html(
        summary_html=summary_html,
        model=model,
        has_backend=backend_src.is_dir(),
        has_vitest=vitest_html.is_dir(),
        has_frontend=frontend_cov.is_dir(),
        mocked_n=mocked_n,
        e2e_n=e2e_n,
        e2e_instrumented=e2e_instrumented,
    )
    (htdocs / "index.html").write_text(index_html, encoding="utf-8")
    code_cov = htdocs / "code-coverage"
    code_cov.mkdir(exist_ok=True)
    (code_cov / "index.html").write_text(index_html, encoding="utf-8")

    meta = {
        "backend_lines_pct": result.backend_lines_pct,
        "vitest_lines_pct": result.vitest_lines_pct,
        "mocked_playwright_dumps": mocked_n,
        "e2e_playwright_dumps": e2e_n,
        "partial": model.partial,
        "partial_reason": model.partial_reason,
        "surfaces": [
            {
                "surface_id": s.surface_id,
                "label": s.label,
                "lines_pct": s.lines_pct,
                "backend_lines_pct": s.backend_lines_pct,
                "raw_dump_count": s.raw_dump_count,
                "file_count": s.file_count,
            }
            for s in model.surfaces
        ],
    }
    (config.dashboard_root / "meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )
    return htdocs


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _fmt_surface_lines(surface: SurfaceSnapshot) -> str:
    """Playwright rows show frontend (Istanbul) and backend (``apps/api``) when collected."""
    if surface.surface_id in ("playwright_mocked", "playwright_e2e"):
        fe = html.escape(_fmt_pct(surface.lines_pct))
        if surface.surface_id == "playwright_mocked":
            be = html.escape(
                "n/a"
                if surface.backend_lines_pct is None
                else _fmt_pct(surface.backend_lines_pct)
            )
        else:
            be = html.escape(_fmt_pct(surface.backend_lines_pct))
        return f'{fe} <span class="meta">(FE)</span> · {be} <span class="meta">(BE)</span>'
    return html.escape(_fmt_pct(surface.lines_pct))


def _summary_panel(model: UnifiedCoverageModel) -> str:
    status = (
        f"partial — {html.escape(model.partial_reason)}"
        if model.partial
        else "complete"
    )
    rows = "\n".join(
        f"<tr><td>{html.escape(s.label)}</td>"
        f"<td>{_fmt_surface_lines(s)}</td></tr>"
        for s in model.overview_rows()
    )
    e2e_note = ""
    if not model.e2e_instrumented:
        e2e_note = (
            "<p class=\"meta\">E2E Playwright surfaces omitted "
            "(<code>RESALL_COV_E2E_INSTRUMENT=0</code>).</p>"
        )
    return f"""
    <section class="panel active" id="panel-overview">
      <h2>Overview</h2>
      <p class="meta">Generated after <code>resall --cov</code> (Stage 2a digesters). Status: <strong>{status}</strong></p>
      <table>
        <tr><th>Surface</th><th>Lines <span class="meta">(FE · BE for Playwright)</span></th></tr>
        {rows}
      </table>
      {e2e_note}
    </section>
    """


def _playwright_panel(
    model: UnifiedCoverageModel,
    *,
    mocked_n: int,
    e2e_n: int,
    e2e_instrumented: bool,
) -> str:
    mocked = model.by_id("playwright_mocked")
    e2e = model.by_id("playwright_e2e")
    def _pw_line(surface: SurfaceSnapshot | None, n: int, label: str) -> str:
        if not surface and n <= 0:
            return f"{label}: no dumps."
        dumps = surface.raw_dump_count if surface and surface.raw_dump_count is not None else n
        fe = _fmt_pct(surface.lines_pct if surface else None)
        be = _fmt_pct(surface.backend_lines_pct if surface else None)
        if surface and surface.surface_id == "playwright_mocked" and surface.backend_lines_pct is None:
            be = "n/a (no .coverage.e2e.mocked)"
        return (
            f"{label}: <strong>{dumps}</strong> dump(s), "
            f"frontend {fe}, backend {be}."
        )

    mocked_line = _pw_line(mocked, mocked_n, "Mocked")
    if e2e_instrumented:
        e2e_line = _pw_line(e2e, e2e_n, "E2E")
    else:
        e2e_line = "E2E: not instrumented (<code>RESALL_COV_E2E_INSTRUMENT=0</code>)."
    return f"""
    <section class="panel" id="panel-playwright">
      <h2>Playwright (Istanbul raw)</h2>
      <p>{mocked_line}</p>
      <p>{e2e_line}</p>
      <p class="meta">Raw JSON under <code>tests/coverage/artifacts/frontend/playwright-raw/</code>.
        E2E backend % merges <code>.coverage.e2e.*</code> (excluding <code>.coverage.e2e.mocked</code>).
        Mocked <code>--cov</code> uses instrumented SQLite API → <code>.coverage.e2e.mocked</code>. Istanbul FE % is approximate.</p>
    </section>
    """


def _shell_html(
    *,
    summary_html: str,
    model: UnifiedCoverageModel,
    has_backend: bool,
    has_vitest: bool,
    has_frontend: bool,
    mocked_n: int,
    e2e_n: int,
    e2e_instrumented: bool,
) -> str:
    nav_items = ['<button type="button" data-panel="overview" class="active">Overview</button>']
    panels = [summary_html]

    if has_backend:
        nav_items.append('<button type="button" data-panel="backend">Backend</button>')
        panels.append(
            """
    <section class="panel" id="panel-backend">
      <h2>Backend (coverage.py)</h2>
      <iframe class="report-frame" title="Backend coverage"
        src="reports/backend/index.html"></iframe>
    </section>
            """
        )

    if has_vitest:
        nav_items.append('<button type="button" data-panel="vitest">Vitest</button>')
        panels.append(
            """
    <section class="panel" id="panel-vitest">
      <h2>Frontend — Vitest</h2>
      <iframe class="report-frame" title="Vitest coverage"
        src="reports/frontend/vitest-html/index.html"></iframe>
    </section>
            """
        )
    elif has_frontend:
        nav_items.append('<button type="button" data-panel="vitest">Vitest / frontend</button>')
        panels.append(
            """
    <section class="panel" id="panel-vitest">
      <h2>Frontend</h2>
      <p class="meta">Vitest HTML subdir <code>vitest-html/</code> not found; showing landing page.</p>
      <iframe class="report-frame" title="Frontend coverage"
        src="reports/frontend/index.html"></iframe>
    </section>
            """
        )

    nav_items.append('<button type="button" data-panel="playwright">Playwright raw</button>')
    panels.append(
        _playwright_panel(
            model,
            mocked_n=mocked_n,
            e2e_n=e2e_n,
            e2e_instrumented=e2e_instrumented,
        )
    )

    nav = "\n".join(nav_items)
    body = "\n".join(panels)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Code coverage — resall</title>
  <style>
    :root {{
      --bg: #0f1419;
      --nav: #1a2332;
      --accent: #1976d2;
      --text: #e8eaed;
      --muted: #9aa0a6;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    .layout {{ display: flex; min-height: 100vh; }}
    nav {{
      width: 220px; background: var(--nav); padding: 1rem 0.75rem;
      border-right: 1px solid #2a3544; flex-shrink: 0;
    }}
    nav h1 {{ font-size: 1rem; margin: 0 0 1rem; color: #90caf9; font-weight: 600; }}
    nav button {{
      display: block; width: 100%; text-align: left; margin: 0.25rem 0;
      padding: 0.5rem 0.75rem; border: none; border-radius: 6px;
      background: transparent; color: var(--text); cursor: pointer; font-size: 0.9rem;
    }}
    nav button:hover {{ background: #243044; }}
    nav button.active {{ background: var(--accent); color: white; }}
    main {{ flex: 1; padding: 1.25rem; overflow: auto; }}
    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .panel h2 {{ margin-top: 0; font-size: 1.15rem; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #2a3544; padding: 0.5rem 0.75rem; text-align: left; }}
    th {{ background: #1e2a3a; }}
    .report-frame {{
      width: 100%; height: calc(100vh - 6rem); border: 1px solid #2a3544;
      border-radius: 8px; background: white;
    }}
  </style>
</head>
<body>
  <div class="layout">
    <nav>
      <h1>Code coverage</h1>
      {nav}
    </nav>
    <main>
      {body}
    </main>
  </div>
  <script>
    document.querySelectorAll("nav button[data-panel]").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        const id = btn.getAttribute("data-panel");
        document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        const panel = document.getElementById("panel-" + id);
        if (panel) panel.classList.add("active");
      }});
    }});
  </script>
</body>
</html>
"""
