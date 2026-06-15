# Playwright E2E (`tests/e2e/`)

Browser tests for the FRU Analytics Assistant (Vite UI + live API). Scenarios **S1–S5** are defined once in `support/scenarios.ts`.

## Prerequisites

1. Local stack running:

```bash
python orchestrator.py deploy --provider local --scope nonkube
```

2. `.env` with agent + embedding keys (`USE_AGENT_QUERY=true`, `OPENAI_API_KEY`, chat model keys).
3. One-time browser install:

```bash
cd tests/e2e && npm install && npx playwright install chromium
```

## Run

```bash
cd tests/e2e
PLAYWRIGHT_EXTERNAL_STACK=1 npm run test:e2e:full-stack
```

Shell smoke only (no LLM queries):

```bash
PLAYWRIGHT_EXTERNAL_STACK=1 npm run test:e2e:shell
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `PLAYWRIGHT_EXTERNAL_STACK` | — | **Required** `1` — stack started by orchestrator |
| `E2E_FRONTEND_PORT` | `5174` nonkube / `5173` kube | Vite port from `local_deploy_config.yaml` |
| `E2E_API_PORT` | `5001` / `30080` | API port (also `INTEGRATION_API_BASE_URL`) |
| `E2E_DEPLOY_SCOPE` | `nonkube` | `nonkube` or `kube` for YAML port lookup |
| `E2E_QUERY_TIMEOUT_MS` | `180000` | Per-test timeout for LLM queries |
| `PLAYWRIGHT_SLOW_MO_DELAY` | — | Demo pacing (ms) |
| `PLAYWRIGHT_RETRIES` | `0` | Set `1` locally only if flaky |
| `PLAYWRIGHT_HEADLESS` | `1` | Set `0` to watch browser |

## Layout

| Path | Role |
|------|------|
| `browser/full-stack/` | Live stack specs |
| `helpers/core/` | Stack guard, step log |
| `helpers/ui/` | Chat, tabs, Data Management, panels |
| `domain/chat/` | `runChatScenario` |
| `domain/crud/` | S5 `runSuperSaleJourney` |
| `support/scenarios.ts` | Canonical queries + F900 fixture |

Live stakeholder demos: [`demos/playwright_e2e/README.md`](../../demos/playwright_e2e/README.md) — **one** narrated tour test (S0–outro), `strict: false`, S1–S4 on a single page load; not a CI gate.

## Scenarios

| ID | Query | Notes |
|----|-------|-------|
| S1 | Average rating | SQL aggregate; soft numeric match |
| S2 | Best state by revenue | Expect CA / California |
| S3 | Best city by revenue | Houston / Kansas City on seed data |
| S4 | Top 3 complaint areas | Semantic themes |
| S5 | CRUD + best city | Inserts **F900** $70k NYC sale; deletes after |

S5 skips when embedding POST fails (same as `tests/integration/crud/test_rawdata_crud.py`).
