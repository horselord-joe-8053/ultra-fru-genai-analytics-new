# Refactor Next Steps — env_utils In-Place

**Refactor completed:** Phases A–E, G (env_utils in-place with cloud_shared and gcp).

---

## What Was Done

| Phase | Changes |
|-------|---------|
| **A** | Added `env_utils/cloud_shared/` with `LLMClient`, `StorageBackend`, `provider.py`, `credentials.py` |
| **B** | Added `env_utils/gcp/` placeholder |
| **C** | Health endpoint uses `check_credentials_status()` — no direct boto3 in app.py |
| **D** | Agent uses `llm_client=create_llm_client()` instead of `bedrock_client=get_bedrock_client()` |
| **E** | Filesystem uses `get_storage_backend(path)` — no direct s3_helpers import |
| **G** | Updated docs and package docstrings |

---

## Next Steps to Test

### 1. Run API locally (health + agent)

```bash
cd /path/to/fru-genai-analytics-new
# Ensure .env has required vars (PGHOST, PGPASSWORD, OPENAI_API_KEY, etc.)
# For AWS: CLOUD_REGION, AWS_BEDROCK_* or CLAUDE_API_KEY for local
PYTHONPATH=core_app python -m flask --app backend.api.app run --port 5001
```

Then:

```bash
curl http://localhost:5001/health
```

**Expected:** JSON with `database`, `openai`, and credentials status (`aws`, `gcp`, or `local`). No boto3 import in app.py.

### 2. Test agent query (if DB + LLM configured)

```bash
curl -X POST http://localhost:5001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many fridges were sold?"}'
```

**Expected:** Agent uses `create_llm_client()` (Bedrock or local Claude per env).

### 3. Test filesystem (S3 path — requires AWS creds)

```bash
PYTHONPATH=core_app python -c "
from backend.utils.filesystem import exists, listdir
# Use a real S3 path if you have one
# exists('s3://your-bucket/prefix/')
# Or local:
print(exists('/tmp'))
print(listdir('/tmp')[:3])
"
```

### 4. Build Docker image (no Dockerfile changes)

```bash
cd /path/to/fru-genai-analytics-new
docker build -t fru-api-test -f core_app/Dockerfile core_app
```

**Expected:** Build succeeds. `COPY backend` includes env_utils (cloud_shared, gcp, etc.).

### 5. Run deploy (optional)

```bash
.venv/bin/python orchestrator.py deploy --scope kube --env dev
```

**Expected:** Build, push, and deploy work. Health and query endpoints behave as before.

---

## Verification Checklist

- [ ] `curl /health` returns credentials status (aws/gcp/local)
- [ ] Agent query works with `create_llm_client()`
- [ ] `filesystem.exists('/tmp')` works
- [ ] `filesystem.exists('s3://...')` works (with AWS creds)
- [ ] Docker build succeeds
- [ ] No `import boto3` in `backend/api/app.py`
- [ ] No `from backend.env_utils.aws.s3_helpers` in `backend/utils/filesystem.py`

---

## Future Work (GCP Phase 1)

When implementing GCP:

1. Add `env_utils/gcp/gcs_helpers.py` — `gcs_exists`, `gcs_listdir`, `gcs_isdir`
2. Add `GCSStorageBackend` in `env_utils/gcp/storage_backend.py`
3. Update `storage_factory.get_storage_backend()` to return `GCSStorageBackend` for `gs://`
4. Add `env_utils/gcp/gemini_api_client.py` implementing `LLMClient`
5. Extend `client_factory.create_llm_client()` with GCP branch

See [REFACTOR_PLAN_GCP_READINESS.md](REFACTOR_PLAN_GCP_READINESS.md) Phase 1.
