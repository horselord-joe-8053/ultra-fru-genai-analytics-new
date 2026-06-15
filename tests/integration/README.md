# Integration tests (`tests/integration/`)

HTTP tests against a **running local API** (Docker / `orchestrator.py deploy`). Marked `@pytest.mark.integration`.

## Prerequisites

1. Docker running.
2. `.env` with keys (`OPENAI_API_KEY` when `USE_AGENT_QUERY=true`; embed keys for CRUD/embedding tests).
3. Stack up:

```bash
python orchestrator.py deploy --provider local --scope all
```

## Run

```bash
./scripts/run_integration_tests.sh
# or:
pytest tests/integration -m integration -v
```

Tests **skip** when `/health` is unreachable.

## Layout

| Subfolder | Focus |
|-----------|--------|
| `api/` | Health, version, query stream SSE, execution log |
| `crud/` | `/rawdata` lifecycle (Data Management API) |
| `embeddings/` | Dual-profile sync, ModelArk lane, RDS path |
| `verify/` | `verify_against_local` smoke |

Shared fixtures: `tests/integration/conftest.py` (`base_url`, `require_stack`, `total_rec`).

## Environment

| Variable | Purpose |
|----------|---------|
| `INTEGRATION_API_BASE_URL` | Override API base (default `http://localhost:5001`) |
| `INTEGRATION_QUERY_STREAM_TIMEOUT` | `/query/stream` timeout seconds (default `120`) |
| `EMBEDDING_ACTIVE_PROFILE` | Embedding lane (`openai_1536` default) |

See [`tests/README.md`](../README.md) for the full variable table.
