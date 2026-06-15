# Unit tests (`tests/unit/`)

Fast pytest tests with **no live API**, **no Docker**, and **no LLM calls**. Mock external I/O at boundaries.

## When to add here vs integration vs e2e

| Category | Use when |
|----------|----------|
| **Unit** (`tests/unit/`) | Pure logic, Flask route handlers with mocked DB, env parsing, deploy helper wiring |
| **Integration** (`tests/integration/`) | Live local API + Postgres (`@pytest.mark.integration`) |
| **E2E** (`tests/e2e/`) | Browser Playwright against Vite UI + live stack |

## Run

```bash
pytest -m "not integration"
pytest -m "not integration" --cov --cov-report=term-missing
```

See [`tests/README.md`](../README.md) for coverage and CI notes.

## Layout

| Path | Targets |
|------|---------|
| `tests/unit/core_app/backend/` | Flask API, agents, env_utils, services, ETL |
| `tests/unit/tools/` | Deploy/verify helpers, compose/k8s env wiring |
| `tests/unit/test_orchestrator_env.py` | Orchestrator env bootstrap |

~200 tests collected with `-m "not integration"` (count drifts as suites grow).
