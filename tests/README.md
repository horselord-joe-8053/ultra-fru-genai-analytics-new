# Tests

Pytest suite for FRU GenAI Analytics. **Unit** tests mock external I/O; **integration** tests hit a live local API (Docker).

## Unit tests (default PR / CI)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -m "not integration"
pytest -m "not integration" --cov --cov-report=term-missing
```

If `pytest` reports `unrecognized arguments: --cov`, unset `PYTEST_DISABLE_PLUGIN_AUTOLOAD` in your shell (some dev environments set it to `1`).

## Integration tests (Docker + local deploy)

**Prerequisites**

1. Docker Desktop (or Docker Engine) running.
2. `.env` with keys (at least `OPENAI_API_KEY` if `USE_AGENT_QUERY=true`).
3. Local stack up:

```bash
python orchestrator.py deploy --provider local --scope all
# API: http://localhost:5001/health (LOCAL_SERVER_PORT)
```

**Run**

```bash
./scripts/run_integration_tests.sh
# or:
pytest tests/integration -m integration -v
```

Tests **skip** automatically if `/health` is unreachable (safe when Docker is off).

| Variable | Purpose |
|----------|---------|
| `INTEGRATION_API_BASE_URL` | Override API base (default `http://localhost:${LOCAL_SERVER_PORT}`) |
| `INTEGRATION_FULL_VERIFY=1` | Run full `verify_api_endpoints` (QueryStream + Analytics, needs ETL/data) |
| `INTEGRATION_VERIFY_TIMEOUT_SEC` | Poll timeout for verify helper (default `90` smoke, `300` full) |
| `INTEGRATION_QUERY_STREAM_TIMEOUT` | Per-request timeout for `/query/stream` (default `120`) |
| `INTEGRATION_TOTAL_REC` | Expected row count when CSV path differs |

**CI:** Unit workflow excludes integration (`-m "not integration"`). Optional [`.github/workflows/integration-tests.yml`](../.github/workflows/integration-tests.yml) is **manual** (`workflow_dispatch`) and documents the same prerequisites.

## Layout

| Path | Targets |
|------|---------|
| `tests/unit/core_app/backend/` | Flask API, agents, env_utils |
| `tests/unit/tools/cloud_shared/` | Shared deploy/verify helpers |
| `tests/unit/tools/aws/scope_shared/` | AWS resource names, phases |
| `tests/integration/` | Live local API: health, query stream, shared verify |

## Environment (unit)

`tests/conftest.py` sets minimal env vars before importing `backend.api.app`. Override in a test with `monkeypatch.setenv` when needed.

## Coverage

`.coveragerc` enforces staged `fail_under` (raise as coverage grows). CI runs `pytest --cov` on push/PR for unit tests only.
