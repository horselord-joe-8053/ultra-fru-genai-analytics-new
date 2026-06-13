<h1 id="doc-title" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">Using <code>coverage_kit</code> (portable coverage reporters)</h1>

**Type:** how-to — copy the whole **`utils/coverage_kit/`** tree (Python reporters + **`collectors/`** TypeScript subpackage) to another repository (same pattern as **`neat_logger`**).

**Project home (Floor35):** **`tests/coverage/README.md`**.

---

<h2 id="doc-outline">Document outline</h2>

1. [Collectors vs reporters](#collectors)
 1.1 [TypeScript collectors (`collectors/`)](#collectors-ts)
2. [Portable env contract](#env)
3. [Artifact layout](#artifacts)
4. [Bootstrap (new repo)](#bootstrap)
5. [Files to copy](#copy)

---

<h2 id="collectors">1. Collectors vs reporters</h2>

| Layer | Responsibility | Examples |
|-------|----------------|----------|
| **Collectors** | Run tests with instrumentation | `coverage run`, Vitest `test:coverage`, Playwright + `VITE_COVERAGE` |
| **Reporters** | Combine data, HTML, ops-log summary | **`utils/coverage_kit/reporters/`** (e.g. **`finalize.py`**) |

Project code owns collectors; the kit owns finalize.

<h3 id="collectors-ts" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.1 TypeScript collectors (`collectors/`)</h3>

NPM package **`@floor35/coverage-collectors`** at **`utils/coverage_kit/collectors/`** (paths + Playwright Istanbul dump). See **`collectors/README.md`**.

```json
{
  "dependencies": {
    "@floor35/coverage-collectors": "file:../../utils/coverage_kit/collectors"
  }
}
```

| Export | Use when |
|--------|----------|
| `paths` | Vitest `reportsDirectory`, exclude glob, `FRONTEND_COVERAGE_DIR` |
| `playwright-dump` | `dumpPlaywrightCoverage(page, outPath)` when `PW_COLLECT_COVERAGE=1` |

Peer: `@playwright/test` when using **`playwright-dump`**. Vitest config often imports **`../../utils/coverage_kit/collectors/paths`** by relative path (Vite config loader).

---

<h2 id="env">2. Portable env contract</h2>

| Portable | This repo alias | Default |
|----------|-----------------|---------|
| `COV_EMIT_HTML` | `RESALL_COV_EMIT_HTML` | `1` |
| `COV_LOG_REPORT_MAX_LINES` | `RESALL_COV_LOG_REPORT_MAX_LINES` | `40` |
| `COV_E2E_INSTRUMENT` | `RESALL_COV_E2E_INSTRUMENT` | `0` |
| `COV_DASHBOARD_PORT` | `RESALL_COV_DASHBOARD_PORT` | `5199` |
| `COV_DASHBOARD_BIND` | `RESALL_COV_DASHBOARD_BIND` | `127.0.0.1` |
| `COV_FRONTEND_COVERAGE_DIR` | `FRONTEND_COVERAGE_DIR` | `tests/coverage/artifacts/frontend` (under **repo root**) |
| `COV_DATA_DELETE_AFTER_MERGED` | `RESALL_COV_DATA_DELETE_AFTER_MERGED` | `0` — keep per-phase `.coverage.*` after combine; `1` deletes inputs |

---

<h2 id="artifacts">3. Artifact layout</h2>

| Artifact | Portable path |
|----------|----------------|
| Backend data | `.coverage.phase01`, `.coverage.phase02`, `.coverage.e2e.*` |
| Backend config | `tests/coverage/.coveragerc` |
| Backend data | `tests/coverage/artifacts/backend/data/.coverage*` |
| Backend HTML | `tests/coverage/artifacts/backend/api-htmlcov/index.html` |
| Frontend Vitest | `{repo_root}/{FRONTEND_COVERAGE_DIR}/` (this repo: `tests/coverage/artifacts/frontend/`) |
| Vitest summary JSON | `{repo_root}/{FRONTEND_COVERAGE_DIR}/coverage-summary.json` |
| Playwright raw | `{repo_root}/{FRONTEND_COVERAGE_DIR}/playwright-raw/*.json` |
| Frontend landing | `{repo_root}/{FRONTEND_COVERAGE_DIR}/index.html` |
| Vitest HTML (subdir) | `{repo_root}/{FRONTEND_COVERAGE_DIR}/vitest-html/index.html` |
| Stitched dashboard (Stage 1) | `tests/coverage/artifacts/backend/dashboard/htdocs/index.html` |
| Dashboard session marker | `tests/coverage/artifacts/backend/dashboard/.resall-cov-session.json` |

**Stage 1 dashboard:** The stitched site lives under **`tests/coverage/artifacts/backend/dashboard/htdocs/`** and is served on demand at **`127.0.0.1:5199`**. In **this repo**, **`ops/local/run_cov_dashboard.py`** owns idempotent start/stop for both one-shot verify and persistent `run_all` lifecycle. No auth in Stage 1.

| Action | Collectors? | Reporters? | Server |
|--------|-------------|------------|--------|
| `resall --cov` | yes (phases 1–4 + opt E2E) | finalize at end | one-shot start/verify/stop in phase 14 |
| `test-* --cov` | yes (one suite) | optional `cov-finalize` | no automatic persistent server |
| `cov-finalize` | **no** | yes | no server side effect |
| `run_all start` / `restart` | **no** | `cov-finalize` if artifacts else warn | start **:5199** persistently |
| `run_all stop` | — | — | stop **:5199** |

**Incremental workflow:** Re-run any subset of collectors (`test-vitest --cov`, etc.), then **`cov-finalize`** to refresh HTML and the dashboard without a full **`resall --cov`**. Stale `.coverage.phase*` files are still combined unless you re-ran phases 1–2.

**Artifact cleanup:** **`resall --cov` does not wipe** `tests/coverage/artifacts/` at ritual start. That keeps incremental **`cov-finalize`** fast but can leave stale datafiles after refactors — clear `tests/coverage/artifacts/backend/data/` and frontend artifacts manually (or re-run collectors 1–4) when numbers look wrong. **`COV_DATA_DELETE_AFTER_MERGED=0`** (default) keeps per-phase inputs after combine; set **`1`** to let combine delete them.

**Stage 2a (implemented):** OOP **`CoverageDigester`** hierarchy under **`utils/coverage_kit/reporters/digesters/`** builds a **`UnifiedCoverageModel`** (per-surface line %, file lists where available, partial flags). **`reporters/dashboard_build.py`** renders the overview table and Playwright panel from the model; deep HTML still uses iframe links to **`reports/backend/`** and **`reports/frontend/`**. Playwright **E2E** rows show **frontend (Istanbul)** and **backend (`apps/api`)** line % (backend merges all **`.coverage.e2e.*`** from instrumented stacks). **Mocked** Playwright with **`test-e2e-mocked --cov`**: instrumented SQLite API (``.coverage.e2e.mocked``) + real API pass-through; mock-only specs skip under **`PW_PASS_API_TO_BACKEND`**. Without **`--cov`**, mocked specs use in-browser JSON mocks (frontend Istanbul only). **`build_unified_coverage_model(config, finalize=…)`** backfills headline % from finalize when HTML/JSON is missing. Collectors and **`COV_*`** / **`RESALL_COV_*`** env names are unchanged.

**Stage 2b (optional):** Cross-tool merged line metrics (backend + Vitest + Playwright Istanbul). **Do not implement until a feasibility/accuracy review** confirms merged numbers are trustworthy (Istanbul chunk limits, duplicate instrumentation, path mapping).

---

<h2 id="bootstrap">4. Bootstrap (new repo)</h2>

1. Copy **`utils/coverage_kit/`** (including **`collectors/`**) and **`.cursor/rules/coverage-kit.mdc`** (optional).
2. Ensure repo root is on **`sys.path`** for `from utils.coverage_kit import …`.
3. Add env vars to **`.env.example`** (portable or project names).
4. Point phase-1/2 collectors at **`.coverage.phase01`** / **`.coverage.phase02`** via **`COVERAGE_FILE`**.
5. Implement a thin **adapter** module (e.g. `finalize_my_ritual_cov_reports`) calling **`finalize_coverage`** with **`default_config(repo_root)`** customized if paths differ.
6. Call finalize **after** the test ritual, even on failure (**partial** summary).
7. Wire Vitest **`json-summary`** reporter for **`coverage-summary.json`**; put HTML under **`vitest-html/`** so the landing **`index.html`** is not overwritten.
8. Use **`dashboard_build.py`** / **`dashboard_serve.py`** for stitched local UI.
9. For Playwright: set **`PW_COLLECT_COVERAGE=1`** + **`VITE_COVERAGE=true`**; dump **`window.__coverage__`** to **`playwright-raw/`**.
10. Document open paths in project **`tests/README.md`** or ops README.
11. Add unit tests for env parsing, dashboard index build, HTTP verify, and summary line order.
12. Optional **resall phase 14**: `test-cov-dashboard --cov` — HTTP + Playwright against the stitched dashboard (after finalize).
13. **Standalone finalize** (no tests): `uv run python ops/local/run_all.py cov-finalize` — combine HTML + dashboard from artifacts left by `test-* --cov` or partial `resall --cov`.

---

<h2 id="copy">5. Files to copy</h2>

| Path | Required |
|------|----------|
| `utils/coverage_kit/reporters/` | yes (Python reporters) |
| `utils/coverage_kit/__init__.py` | yes (stable re-exports) |
| `utils/coverage_kit/collectors/` | yes (TS collectors + `package.json`) |
| `utils/coverage_kit/HOWTO_USE_COVERAGE_KIT.md` | yes |
| `utils/coverage_kit/collectors/README.md` | recommended |
| `.cursor/rules/coverage-kit.mdc` | recommended |
