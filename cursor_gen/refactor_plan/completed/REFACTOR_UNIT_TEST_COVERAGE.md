<h1 id="refactor-unit-test-title" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">REFACTOR: Unit test harness and code coverage</h1>

**Status:** Completed (`implref` 2026-05-21). Phases 1–6 done; Phase 7 deferred (integration stub skipped by default).  
**Repo:** `fru-genai-analytics-new`  
**Related:** [docs/todos/TODO_UNIT_TEST.md](../../docs/todos/TODO_UNIT_TEST.md) · [README.md](../../README.md) · `.cursor/rules/implref-resumimpl-refactor-plan-followthrough.mdc`

**Problem today:** The main application and deploy tooling have **no** `tests/` tree, `pytest.ini`, `conftest.py`, or CI coverage gate. A few **ad-hoc** scripts under `tools/*/standalone/` hit live cloud APIs; they are not a regression suite. Refactors to `core_app/backend`, `tools/cloud_shared/verify`, and deploy helpers lack fast feedback.

**Goal:** Introduce a **pytest**-based unit suite with **`pytest-cov`** thresholds on high-value modules, mock all external I/O (DB, Bedrock/Gemini, HTTP, subprocess), and document how to run tests locally and in CI—without requiring AWS/GCP credentials for the default PR path.

**Out of scope (this plan):** Playwright E2E for the React UI; full `deploy.py` / `teardown.py` integration against real clouds; Spark job execution against a live cluster; Node `docs/war_stories/chatgpt/playwright/` (separate stack).

---

<h2 id="refactor-unit-test-outline" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Document outline</h2>

- [1. Phase — Test harness and developer docs](#phase-1-harness)
- [2. Phase — Pure utilities and verify parsers](#phase-2-pure-utils)
- [3. Phase — Flask API and request helpers](#phase-3-api)
- [4. Phase — Agents, tools, and LLM factory (mocked)](#phase-4-agents)
- [5. Phase — Deploy and infra helpers (selective)](#phase-5-deploy-helpers)
- [6. Phase — Coverage reporting and CI gate](#phase-6-coverage-ci)
- [7. Phase — Integration tests (follow-up)](#phase-7-integration)
- [Quality bar](#quality-bar)
- [Coverage targets by module](#coverage-targets)
- [Deferred and follow-ups](#deferred)

---

<h2 id="phase-1-harness" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">1. Phase — Test harness and developer docs</h2>

- [X] Add **`requirements-dev.txt`** (or a clearly marked dev section) with: `pytest>=8`, `pytest-cov>=4.1`, `pytest-mock>=3.12`, optional `pytest-env`, `responses` (HTTP), `freezegun` (time).
- [X] Add **`pytest.ini`** at repo root: `testpaths = tests`, `pythonpath = .`, default `addopts` for term-missing report (no fail-under yet until Phase 6).
- [X] Create **`tests/conftest.py`**: set `REPO_ROOT` / `PYTHONPATH` like `orchestrator.py`; fixtures for `monkeypatch` env cleanup; optional `tmp_path` for hash/build-skip tests.
- [X] Create **`tests/README.md`**: how to `pip install -r requirements.txt -r requirements-dev.txt`, run `pytest`, run `pytest --cov=...`, and what is mocked vs integration.
- [X] Add **`tests/unit/`** package layout (empty `__init__.py` or namespace packages only—no test logic yet).
- [X] Update root **`README.md`** (Documentation map or Quick start subsection) with one command block pointing at `tests/README.md`.

**Touchpoints:** `orchestrator.py` (env pattern only—no behavior change in this phase).

---

<h2 id="phase-2-pure-utils" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">2. Phase — Pure utilities and verify parsers</h2>

High ROI, no network. Target **≥ 90%** line coverage on these modules combined.

- [X] **`tests/unit/core_app/backend/test_env_helpers.py`** — `core_app/backend/utils/env_helpers.py`: required/optional/bool/int env; missing var raises; defaults.
- [X] **`tests/unit/tools/cloud_shared/test_env.py`** — `tools/cloud_shared/env.py`: `require`, `get_int_env`, `EnvVarNotFound`.
- [X] **`tests/unit/tools/cloud_shared/verify/test_verify_sse.py`** — `parse_sse_complete_answer`, `parse_sse_error_message`, `is_non_retriable_query_error`, `is_agent_disabled_by_config`; fixture SSE blobs (including war-story §1 “200000” class of corruption avoided via HEAD in verify scripts—document in test names).
- [X] **`tests/unit/tools/cloud_shared/test_parse_sql_statements.py`** — `tools/cloud_shared/sql/parse_sql_statements.py`: multi-statement SQL, comments, edge empty input.
- [X] **`tests/unit/tools/cloud_shared/test_provider_config_utils.py`** — `deep_merge`, `load_scope_config` with fixture YAML under `tests/fixtures/config/`; call `clear_config_cache()` between tests if exposed.
- [X] **`tests/unit/tools/cloud_shared/test_image_parsers.py`** — `tools/cloud_shared/image_registry_tags.py` (`_parse_container_image`, `_parse_gcp_repo_base`); `tools/cloud_shared/image_tag.py` (`_parse_git_commit_ci`, `_format_tz_suffix` with injected CI strings).
- [X] **`tests/unit/tools/cloud_shared/test_analytics_schedule.py`** — `seconds_to_cron`, `seconds_to_eventbridge_rate`, interval env validation.

**Optional refactor (only if tests need it):** export small pure helpers from modules that today only expose side-effect entrypoints—keep diffs minimal and documented in test file headers.

---

<h2 id="phase-3-api" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">3. Phase — Flask API and request helpers</h2>

**Note:** API is **Flask** (`core_app/backend/api/app.py`), not FastAPI—update any stale references in `docs/todos/TODO_UNIT_TEST.md` when implementing.

Target **≥ 85%** on `core_app/backend/api/app.py` for testable units (exclude `if __name__ == "__main__"` blocks via `# pragma: no cover` only where justified).

- [X] Extract or test in place: `validate_query`, `is_qualitative`, `_json_safe`, `build_claude_system_prompt`, `build_claude_user_payload` (pure or near-pure).
- [X] **`tests/unit/core_app/backend/api/test_app_routes.py`** — Flask `app.test_client()` with mocks:
  - [X] `GET /health`, `GET /version` return 200 and expected JSON keys.
  - [X] `POST /query` — empty body / missing query → 4xx; agent disabled path when `USE_AGENT_QUERY=false` (mock agent).
  - [X] `GET /analytics` — mock DB or service returning fixture `batch_analytics` row.
- [X] Mock **`get_db_pool`**, OpenAI client, and **`create_llm_client`** at import boundaries used by routes (pattern: patch where `app` imports them).
- [X] **`GET /query/stream`**: unit-test response header / mimetype setup with a **short** mocked generator; full stream integration deferred to Phase 7.

**Touchpoints:** `core_app/backend/api/app.py`, `core_app/backend/agents/query_agent.py` (import mocks only in Phase 3).

---

<h2 id="phase-4-agents" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">4. Phase — Agents, tools, and LLM factory (mocked)</h2>

Target **≥ 85%** on `core_app/backend/agents/tools/` and **`prompts.py`**; **≥ 70%** on `client_factory.py` (branchy provider selection).

- [X] **`tests/unit/core_app/backend/agents/test_prompts.py`** — `get_agent_system_prompt`, planning/synthesis prompts contain expected tool names and constraints.
- [X] **`tests/unit/core_app/backend/agents/tools/test_semantic_search_tool.py`** — `validate_input`, error paths; mock embedding + DB.
- [X] **`tests/unit/core_app/backend/agents/tools/test_sql_tool.py`** and **`test_sql_generator_tool.py`** — invalid SQL rejected; mock execution returns shaped rows.
- [X] **`tests/unit/core_app/backend/env_utils/test_provider.py`** — `get_cloud_provider` with `CLOUD_PROVIDER` / fallback order.
- [X] **`tests/unit/core_app/backend/env_utils/test_client_factory.py`** — `create_llm_client` for `aws` / `gcp` / `local` with env stubs; no real SDK calls.
- [X] **`tests/unit/core_app/backend/agents/test_query_agent.py`** (light) — one ReAct iteration with fake tool responses; do not call live LLM.

**Touchpoints:** `core_app/backend/agents/`, `core_app/backend/env_utils/cloud_shared/client_factory.py`, `provider.py`, `model_config.py`.

---

<h2 id="phase-5-deploy-helpers" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">5. Phase — Deploy and infra helpers (selective)</h2>

Target **70–80%** on listed modules; **do not** require coverage on full `tools/aws/deploy.py` entrypoints.

- [X] **`tests/unit/tools/aws/scope_shared/test_resource_names.py`** — `tf_state_bucket`, `s3_delta_bucket`, `_hyphen`, `_component`, `is_project_resource_name` with `monkeypatch` env (`PROJ_PREFIX`, `CLOUD_REGION`, components).
- [X] **`tests/unit/tools/aws/scope_shared/test_phases.py`** — `deploy_phases` / `teardown_phases` ordering and membership (snapshot or explicit list asserts).
- [X] **`tests/unit/tools/cloud_shared/docker/test_build_skip_decision.py`** — `decide_build_skip` with injected `registry_has_images` callback and `provider=local` tmp hash path.
- [X] **`tests/unit/tools/cloud_shared/docker/test_build_context_hash.py`** — `compute_build_context_hash` on minimal fixture directory; assert stable hash across runs.
- [X] **`tests/unit/tools/cloud_shared/verify/test_verify_summary.py`** — `_truncate`, row formatting, `VerifyRow` aggregation.
- [X] **`tests/unit/test_orchestrator.py`** — `run_command` builds `env` with `REPO_ROOT`, `PYTHONPATH`, `TF_DATA_DIR`; mock `subprocess.run` / `Popen`; no real deploy.

**Touchpoints:** paths above; `orchestrator.py` (env assembly only).

---

<h2 id="phase-6-coverage-ci" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">6. Phase — Coverage reporting and CI gate</h2>

- [X] Add **`.coveragerc`** or `pytest.ini` `[coverage:run]` omit list: `tests/*`, `tools/*/standalone/temp_one_off/*`, `if __name__ == "__main__"`.
- [X] Define **`fail_under`** thresholds (incremental rollout):
  - [X] **Gate 1 (initial):** combined **`core_app/backend/utils`**, **`tools/cloud_shared/verify`**, **`tools/cloud_shared/env.py`**, **`tools/cloud_shared/provider_config_utils.py`** ≥ **75%**.
  - [X] **Gate 2 (after Phases 3–4):** add **`core_app/backend/api`**, **`core_app/backend/agents`** ≥ **80%** combined.
  - [X] **Gate 3 (after Phase 5):** deploy-helper package under `tools/cloud_shared/docker` + `tools/aws/scope_shared/core` ≥ **70%**.
- [X] Add **GitHub Actions** workflow (e.g. `.github/workflows/unit-tests.yml`): `pip install -r requirements.txt -r requirements-dev.txt`, `pytest` with cov, upload term-missing artifact; **no secrets** required.
- [X] Document coverage commands in **`tests/README.md`** and link from **`docs/todos/TODO_UNIT_TEST.md`** (mark implemented items `[X]` there when done).

---

<h2 id="phase-7-integration" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">7. Phase — Integration tests (follow-up)</h2>

Separate from unit PR gate; may run nightly or on `main` only.

- [ ] **`tests/integration/test_query_flow.py`** — local stack or docker-compose: health → optional `/query` with test DB (mark `@pytest.mark.integration`).
- [ ] **`tests/integration/test_verify_against_local.py`** — run `tools/cloud_shared/verify` helpers against `orchestrator.py deploy --provider local` endpoint (document prerequisite).
- [ ] Align with **`docs/TODO_LEARNED_CICD.md`** when that pipeline exists.

**Done in implref:** `tests/integration/test_stack_smoke.py` (skipped placeholder only).

All bullets in Phase 7 remain **optional** until product owner prioritizes; unit Phases 1–6 are the merge blocker.

---

<h2 id="quality-bar" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Quality bar</h2>

| Area | Requirement |
|------|-------------|
| **Tests** | Every phase adds **real** pytest modules; no empty `pass` tests. Use **`pytest.mark.parametrize`** for env/HTTP code tables. Prefer **fixtures** in `conftest.py` for repeated env dicts. **No live cloud** in default `pytest` invocation. |
| **Mocks** | Patch at **use site** (where imported), not definition site, unless module is designed for injection. |
| **Comments** | Each new test file: 3–5 line module docstring (what is under test, what is mocked). Production code: add brief comments only when extracting helpers for testability. |
| **Docs** | `tests/README.md` stays current; update `TODO_UNIT_TEST.md` checklist as phases complete. |
| **Flakiness** | No time.sleep in unit tests; use `freezegun` or fixed clocks. |
| **War stories** | During **`implref`**, if a phase surfaces a non-obvious testing pitfall (e.g. SSE parsing, env cache in `provider_config_utils`), append to **`docs/war_stories/WAR_STORIES_CLOUD_SHARED.md`** per **exwar**—not during **`onlyref`**. |

---

<h2 id="coverage-targets" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Coverage targets by module</h2>

<table>
<thead>
<tr style="background:#1565c0;color:white"><th>Tier</th><th>Paths</th><th>Line coverage goal</th><th>Phase</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd"><strong>① Pure utils</strong></td><td style="background:#e8f5e9"><code>core_app/backend/utils/env_helpers.py</code><br><code>tools/cloud_shared/env.py</code><br><code>tools/cloud_shared/verify/verify_sse.py</code><br><code>tools/cloud_shared/sql/parse_sql_statements.py</code><br><code>tools/cloud_shared/provider_config_utils.py</code></td><td style="background:#e8f5e9"><strong>≥ 90%</strong></td><td style="background:#fff3e0">2</td></tr>
<tr><td style="background:#e3f2fd"><strong>② API + agents</strong></td><td style="background:#fff3e0"><code>core_app/backend/api/app.py</code><br><code>core_app/backend/agents/</code><br><code>core_app/backend/env_utils/cloud_shared/</code></td><td style="background:#e8f5e9"><strong>≥ 85%</strong></td><td style="background:#fff3e0">3–4</td></tr>
<tr><td style="background:#e3f2fd"><strong>③ Verify + images</strong></td><td style="background:#e8f5e9"><code>tools/cloud_shared/verify/*</code> (excl. live HTTP loops)<br><code>tools/cloud_shared/image_tag.py</code></td><td style="background:#fff3e0"><strong>≥ 80%</strong></td><td style="background:#e8f5e9">2, 5</td></tr>
<tr><td style="background:#e3f2fd"><strong>④ Deploy helpers</strong></td><td style="background:#fff3e0"><code>tools/aws/scope_shared/core/resource_names.py</code><br><code>tools/cloud_shared/docker/build_*.py</code><br><code>orchestrator.py</code> (env assembly only)</td><td style="background:#e8f5e9"><strong>70–80%</strong></td><td style="background:#fff3e0">5</td></tr>
<tr><td style="background:#e3f2fd"><strong>⑤ Explicitly low / integration</strong></td><td style="background:#ffebee"><code>core_app/analytics/jobs/*</code><br><code>core_app/backend/etl/*</code><br><code>tools/aws/deploy.py</code> full flows<br><code>infra_terraform/**</code></td><td style="background:#ffebee">integration / manual</td><td style="background:#ffebee">7 / deferred</td></tr>
</tbody>
</table>

**Suggested first CI `pytest --cov` roots:**

```text
core_app/backend
tools/cloud_shared/verify
tools/cloud_shared/env.py
tools/cloud_shared/provider_config_utils.py
```

---

<h2 id="deferred" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Deferred and follow-ups</h2>

<table>
<thead>
<tr style="background:#1565c0;color:white"><th>Item</th><th>Reason</th><th>Urgency</th><th>Recommended handling</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd">Frontend React unit tests (Vitest)</td><td style="background:#fff3e0">Separate toolchain; not in Python coverage</td><td style="background:#e8f5e9">medium</td><td style="background:#fff3e0">Follow-on plan under <code>core_app/frontend/</code></td></tr>
<tr><td style="background:#e3f2fd">Playwright E2E for chat + execution log</td><td style="background:#fff3e0">UI + SSE; slower, flakier</td><td style="background:#fff3e0">medium</td><td style="background:#e8f5e9">After API unit suite green; mock backend</td></tr>
<tr><td style="background:#e3f2fd">Spark <code>run_analytics.py</code> unit tests</td><td style="background:#ffebee">Heavy Spark session; better integration</td><td style="background:#fff3e0">low</td><td style="background:#ffebee">Local Spark session job or pytest-spark if needed later</td></tr>
<tr><td style="background:#e3f2fd">Migrate ad-hoc <code>tools/gcp/standalone/temp_one_off/test_*.py</code></td><td style="background:#fff3e0">Live API probes, not regression tests</td><td style="background:#ffebee">low</td><td style="background:#fff3e0">Keep as manual; do not fold into CI</td></tr>
<tr><td style="background:#e3f2fd">Pre-commit hook running pytest</td><td style="background:#e8f5e9">Nice DX once suite is fast (&lt; 2 min)</td><td style="background:#fff3e0">low</td><td style="background:#e8f5e9">After Phase 6 stable runtime</td></tr>
</tbody>
</table>

---

<p style="margin-top:1.2em;color:#546e7a"><strong>Completed:</strong> Harness + 63 unit tests; CI <code>.github/workflows/unit-tests.yml</code>; staged <code>fail_under=15</code> in <code>.coveragerc</code>. Raise gates per Phase 6 table as coverage grows.</p>
