# Tests

Pytest suite and Playwright browser E2E for FRU GenAI Analytics.

## Categories

| Category | Path | Runner | CI default |
|----------|------|--------|--------------|
| **Unit** | `tests/unit/` | pytest | Every PR (`pytest -m "not integration"`) |
| **Integration** | `tests/integration/` | pytest + live API | Manual / nightly |
| **E2E** | `tests/e2e/` | Playwright | Manual (full-stack needs LLM keys) |

Category READMEs: [`unit/README.md`](unit/README.md) · [`integration/README.md`](integration/README.md) · [`e2e/README.md`](e2e/README.md)

Live demos (stakeholder-paced): [`demos/playwright_e2e/README.md`](../demos/playwright_e2e/README.md)

## Unit tests (default PR / CI)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -m "not integration"
pytest -m "not integration" --cov --cov-report=term-missing
```

If `pytest` reports `unrecognized arguments: --cov`, unset `PYTEST_DISABLE_PLUGIN_AUTOLOAD` or pass `-p pytest_cov`.

## Integration tests (Docker + local deploy)

**Prerequisites:** Docker, `.env` keys, `python orchestrator.py deploy --provider local --scope all`

```bash
./scripts/run_integration_tests.sh
pytest tests/integration -m integration -v
```

| Variable | Purpose |
|----------|---------|
| `INTEGRATION_API_BASE_URL` | Override API base (default `http://localhost:5001`) |
| `INTEGRATION_FULL_VERIFY=1` | Full `verify_api_endpoints` |
| `INTEGRATION_VERIFY_TIMEOUT_SEC` | Poll timeout (default `90` smoke, `300` full) |
| `INTEGRATION_QUERY_STREAM_TIMEOUT` | `/query/stream` timeout (default `120`) |
| `INTEGRATION_TOTAL_REC` | Expected row count when CSV path differs |
| `EMBEDDING_ACTIVE_PROFILE` | Embedding lane (`openai_1536` default) |
| `ARK_API_KEY` / `ARK_EMBEDDING_MODEL_ID` | ModelArk integration lane |

## Playwright E2E (browser)

**Prerequisites:** External stack (`PLAYWRIGHT_EXTERNAL_STACK=1`), Vite on `5174` (nonkube) or `5173` (kube).

```bash
./scripts/run_e2e_tests.sh
# or:
cd tests/e2e && npm install && npx playwright install chromium
PLAYWRIGHT_EXTERNAL_STACK=1 npm run test:e2e:full-stack
```

Six tests across three specs (shell + S1–S4 + S5 CRUD). See [`tests/e2e/README.md`](e2e/README.md) for env vars and scenario catalog.

## Layout

| Path | Targets |
|------|---------|
| `tests/unit/core_app/backend/` | Flask API, agents, env_utils, services |
| `tests/unit/tools/` | Deploy/verify helpers |
| `tests/integration/api/` | Live API: health, query, exec log |
| `tests/integration/crud/` | Rawdata CRUD |
| `tests/integration/embeddings/` | Embedding sync lanes |
| `tests/integration/verify/` | Deploy verify smoke |
| `tests/e2e/` | Playwright specs + shared scenario helpers |
| `tests/fixtures/` | Shared YAML snippets |

## Environment (unit)

`tests/conftest.py` sets minimal env vars before importing `backend.api.app`. Override per test with `monkeypatch.setenv`.

## Coverage

`.coveragerc` enforces staged `fail_under`. CI runs `pytest --cov` on unit tests only.
