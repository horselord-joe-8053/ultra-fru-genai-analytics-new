"""Build a simple frontend coverage landing ``index.html`` (O2)."""

from __future__ import annotations

import html
from pathlib import Path

from .frontend_summary import playwright_raw_file_count, read_vitest_summary


def build_frontend_landing_index(
    *,
    landing_path: Path,
    vitest_summary_path: Path,
    vitest_html_subdir: str = "index.html",
    mocked_raw_dir: Path,
    e2e_raw_dir: Path,
    e2e_instrumented: bool,
) -> None:
    """Write landing page with separate sections + combined note."""
    vitest = read_vitest_summary(vitest_summary_path)
    mocked_n = playwright_raw_file_count(mocked_raw_dir)
    e2e_n = playwright_raw_file_count(e2e_raw_dir, prefix="e2e-") if e2e_instrumented else 0

    def pct(v: float | None) -> str:
        return f"{v:.1f}%" if v is not None else "n/a"

    combined_note = (
        "Combined rollup: run <code>nyc merge</code> on compatible Istanbul JSON when needed; "
        "separate sections above are authoritative for this ritual."
    )

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Frontend coverage — resall</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 52rem; }}
    h1 {{ color: #1565c0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th {{ background: #1565c0; color: #fff; text-align: left; padding: 0.5rem; }}
    td {{ border: 1px solid #ccc; padding: 0.5rem; }}
    tr:nth-child(even) td {{ background: #f5f5f5; }}
    .note {{ background: #fff3e0; padding: 0.75rem; border-left: 4px solid #ff8f00; }}
  </style>
</head>
<body>
  <h1>Frontend coverage (resall --cov)</h1>
  <h2>Separate sources</h2>
  <table>
    <thead><tr><th>Source</th><th>Lines</th><th>Detail</th></tr></thead>
    <tbody>
      <tr>
        <td>Vitest (phase 3)</td>
        <td>{html.escape(pct(vitest["lines"]))}</td>
        <td><a href="{html.escape(vitest_html_subdir)}">Vitest HTML report</a></td>
      </tr>
      <tr>
        <td>Mocked Playwright (phase 4)</td>
        <td>n/a</td>
        <td>{mocked_n} raw dump(s) in <code>playwright-raw/</code></td>
      </tr>
      <tr>
        <td>E2E Playwright (phases 5–13)</td>
        <td>n/a</td>
        <td>{"not run (RESALL_COV_E2E_INSTRUMENT=0)" if not e2e_instrumented else f"{e2e_n} dump(s) with prefix e2e-"}</td>
      </tr>
    </tbody>
  </table>
  <h2>Combined</h2>
  <p class="note">{html.escape(combined_note)}</p>
</body>
</html>
"""
    landing_path.parent.mkdir(parents=True, exist_ok=True)
    landing_path.write_text(body, encoding="utf-8")
