# Refactor Plan: DRY db_setup and setup_database

**Goal:** Share schema + load logic between `setup_database.py` (host) and `run_schema_and_load.py` (Cloud Run container) via `db_common.py` and a new `load.py` under `tools/gcp/scope_shared/deploy/db_setup/`.

---

## Current State

| Component | setup_database.py (host) | run_schema_and_load.py (container) |
|-----------|---------------------------|-------------------------------------|
| Schema | `run_schema()` – inline | `db_common.apply_schema()` |
| Load | Subprocess → `load_openai_embeddings_to_pgvector_pg.py` | Inline `_run_load()` |
| Config | Function args (host, port, …) | `db_common.get_db_config()` from env |
| FORCE_DROP_TABLES | `setup_database_utils` | `db_common` (duplicated) |
| Parse SQL | `parse_schema_statements()` subprocess | `parse_sql` in container |

---

## Phase 1: Generalize db_common.py

### 1.1 `apply_schema(conn, schema_path: str, force: bool = False)`

- Add `schema_path` parameter instead of hardcoding `/app/schema.sql`.
- Import `parse_sql_statements` from `tools.cloud_shared.sql.parse_sql_statements` (works on host and in container once we add it to the image).

**Changes:**
- `db_common.py`: Replace `SCHEMA_PATH` with `schema_path` argument.
- `db_common.py`: Use `from tools.cloud_shared.sql.parse_sql_statements import parse_sql_statements`.

### 1.2 `get_db_config(host=None, port=None, user=None, password=None, dbname=None) -> dict`

- Keep env-based defaults.
- Allow overrides for host, port, user, password, dbname when provided.
- Lets `setup_database` pass explicit values for local runs.

**Signature:**
```python
def get_db_config(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    dbname: str | None = None,
) -> dict:
```

### 1.3 Single source for FORCE_DROP_TABLES

- Keep `FORCE_DROP_TABLES` in `setup_database_utils.py` (cloud_shared) – AWS and GCP both use it.
- `db_common.py`: Import from `setup_database_utils` instead of defining its own copy.

---

## Phase 2: Add shared load module

### 2.1 Create `tools/gcp/scope_shared/deploy/db_setup/load.py`

Extract load logic from `run_schema_and_load._run_load()` into a reusable function:

```python
def load_embeddings(
    conn,
    csv_path: str,
    config: dict | None = None,
    force: bool = False,
) -> int:
    """
    Load CSV into fru_sales_embeddings via OpenAI embeddings.
    Returns row count. Idempotent: skips if data exists and not force.
    """
```

- Use `os.getenv()` for OPENAI_API_KEY, OPENAI_EMBED_MODEL, etc. (no `backend.utils.env_helpers`).
- Same logic as current `_run_load()`: pandas, batch loop, OpenAI API, INSERT/ON CONFLICT.
- `config` used only for logging; DB connection is passed in.

### 2.2 Dockerfile

- Add `COPY tools/gcp/scope_shared/deploy/db_setup/load.py /app/load.py`.
- Add `COPY tools/cloud_shared/sql/parse_sql_statements.py` so `db_common` can import it (or keep `parse_sql.py` and ensure `tools.cloud_shared.sql` is on path).

---

## Phase 3: Refactor setup_database.py

### 3.1 Remove `run_schema()` and `load_data()` – call shared logic directly

Do **not** keep `run_schema()` or `load_data()` as wrapper functions. At each call site (--env-only, --use-proxy, direct PGHOST), inline the shared logic:

```python
from tools.gcp.scope_shared.deploy.db_setup.db_common import apply_schema, connect_db, get_db_config
from tools.gcp.scope_shared.deploy.db_setup.load import load_embeddings
from tools.cloud_shared.deploy.setup_database_utils import get_schema_file_path, get_csv_path

config = get_db_config(host=host, port=port, user=user, password=password, dbname=dbname)
conn = connect_db(config)
try:
    apply_schema(conn, schema_path=get_schema_file_path(), force=force)
    load_embeddings(conn, csv_path=get_csv_path(), config=config, force=force)
finally:
    conn.close()
```

- Remove `run_schema()` and `load_data()` entirely.
- Remove subprocess to `load_openai_embeddings_to_pgvector_pg.py`.

---

## Phase 4: Refactor run_schema_and_load.py

### 4.1 Use shared apply_schema and load

- Replace `apply_schema(conn, force=force)` with `apply_schema(conn, schema_path="/app/schema.sql", force=force)`.
- Replace `_run_load()` body with `load_embeddings(conn, csv_path=..., config=config, force=force)`.
- Remove `_run_load`, `_embed_texts`, and related inline load logic.
- Keep `main()` flow: verify_only, schema, check existing count, load or skip, FRU_EMBEDDINGS_COUNT.

---

## Phase 5: Dockerfile and imports

### 5.1 Dockerfile updates – exact COPY lines

Add these lines to `tools/gcp/scope_shared/deploy/db_setup/Dockerfile`:

```dockerfile
# Parse SQL (for db_common.apply_schema) – keep tools structure so import works
COPY tools/cloud_shared/sql/ /app/tools/cloud_shared/sql/

# Shared load logic
COPY tools/gcp/scope_shared/deploy/db_setup/load.py /app/load.py
```

**Exact placement:** After the existing `COPY tools/cloud_shared/logging/...` block and before `# Shared DB utilities`. The `tools/` and `tools/cloud_shared/` dirs already exist from earlier COPYs.

**Why this works:**
- `COPY tools/cloud_shared/sql/ /app/tools/cloud_shared/sql/` copies `parse_sql_statements.py` into `/app/tools/cloud_shared/sql/`.
- With `sys.path.insert(0, "/app")` in `run_schema_and_load.py`, the import `from tools.cloud_shared.sql.parse_sql_statements import parse_sql_statements` resolves correctly.

**Package:** `tools/cloud_shared/sql/__init__.py` exists (empty) so `sql` is a proper package. The `COPY tools/cloud_shared/sql/` will include it.

### 5.2 Remove obsolete parse_sql copy

The current Dockerfile has:
```dockerfile
COPY tools/cloud_shared/sql/parse_sql_statements.py /app/parse_sql.py
```
After adding `COPY tools/cloud_shared/sql/ /app/tools/cloud_shared/sql/`, `db_common` will use `from tools.cloud_shared.sql.parse_sql_statements import parse_sql_statements`. You can remove the `/app/parse_sql.py` copy.

---

## Phase 6: Cleanup

### 6.1 Remove or deprecate

- `db_common.FORCE_DROP_TABLES` – remove; import from `setup_database_utils` (single source for AWS + GCP).
- `setup_database_utils.parse_schema_statements()` – keep for AWS (RDS Data API path); GCP uses `parse_sql_statements` directly via `apply_schema`.

### 6.2 load_openai_embeddings_to_pgvector_pg.py

- Option A: Keep as a thin CLI that calls `load_embeddings()` (if anything still needs to run it as a subprocess).
- Option B: Remove if nothing uses it after refactor. `setup_database` will call `load_embeddings` directly.

---

## File change summary

| File | Action |
|------|--------|
| `db_common.py` | Add `schema_path` to `apply_schema`; add overrides to `get_db_config`; use `tools.cloud_shared.sql.parse_sql_statements` |
| `load.py` (new) | Extract load logic from `run_schema_and_load._run_load` |
| `run_schema_and_load.py` | Call `apply_schema(conn, "/app/schema.sql", force)` and `load_embeddings(...)`; remove `_run_load` |
| `setup_database.py` | Remove `run_schema` and `load_data`; call shared logic directly at each call site (--env-only, --use-proxy, direct PGHOST) |
| `setup_database_utils.py` | Keep `FORCE_DROP_TABLES`; `db_common` imports from here |
| `Dockerfile` | Copy `tools/cloud_shared/sql/`, `load.py` |
| `load_openai_embeddings_to_pgvector_pg.py` | Deprecate or refactor to call `load_embeddings` |

---

## Execution order

1. Phase 1: db_common changes (backward compatible if we add optional params).
2. Phase 2: Create load.py.
3. Phase 4: Refactor run_schema_and_load to use load.py (container path).
4. Phase 5: Dockerfile updates.
5. Phase 3: Refactor setup_database (host path).
6. Phase 6: Cleanup.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Container import path for `tools.cloud_shared.sql` | Add explicit COPY in Dockerfile; verify with a test run |
| `load_openai_embeddings_to_pgvector_pg` used elsewhere | Grep for usages before removing |
| AWS setup_database uses `parse_schema_statements` | Keep it or have it call `parse_sql_statements` + file read |
