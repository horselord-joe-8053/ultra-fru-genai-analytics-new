# Unit tests

Pytest suite for FRU GenAI Analytics. Layout mirrors production packages under `tests/unit/`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
pytest --cov --cov-report=term-missing
```

If `pytest` reports `unrecognized arguments: --cov`, unset `PYTEST_DISABLE_PLUGIN_AUTOLOAD` in your shell (some dev environments set it to `1`).

## Layout

| Path | Targets |
|------|---------|
| `tests/unit/core_app/backend/` | Flask API, agents, env_utils |
| `tests/unit/tools/cloud_shared/` | Shared deploy/verify helpers |
| `tests/unit/tools/aws/scope_shared/` | AWS resource names, phases |
| `tests/integration/` | Optional stack tests (`@pytest.mark.integration`, skipped in default CI) |

## Environment

`tests/conftest.py` sets minimal env vars before importing `backend.api.app`. Override in a test with `monkeypatch.setenv` when needed.

## Coverage

`.coveragerc` enforces staged `fail_under` (raise as coverage grows). CI runs `pytest --cov` on push/PR.
