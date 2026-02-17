# Legacy vs New Project: Functional Comparison

**Date**: 2026-02-10  
**Last Updated**: 2026-02-10 (post-fix re-verification)  
**Purpose**: Identify gaps between `fru-genai-analytics-legacy` and `fru-genai-analytics-new` that could cause runtime or deployment failures.

---

## Executive Summary

| Category | Status | Risk |
|----------|--------|------|
| DB setup (FRU_CSV_PATH) | **Fixed** | Was: Data load would fail |
| Kube API: OPENAI_API_KEY | **Fixed** | Was: Agent/embeddings would fail |
| Kube API: Bedrock, DELTA_*, CONTAINER_TYPE | **Fixed** | Was: Agent + scheduler would fail |
| DB setup: metadata, idempotency | **Fixed** | Was: Redundant loads |
| DB setup: wait-for-pgvector | **Fixed** | Was: Possible race on fresh Aurora |
| Nonkube: Bedrock, DELTA_LAKE_PACKAGE | **Fixed** | Was: ECS lacked scheduler vars |

---

## 1. Database Setup (setup_database.py)

### 1.1 FRU_CSV_PATH – **Fixed**

**Legacy** (`load_data_aws.sh`):
```bash
CSV_FILE="$REPO_ROOT/module_app_core/data/raw/fridge_sales_with_rating.csv"
export FRU_CSV_PATH="${FRU_CSV_PATH:-$CSV_FILE}"
```

**New** (`setup_database.py`): Now sets `FRU_CSV_PATH` to `core_app/data/raw/fridge_sales_with_rating.csv` (absolute path) and `PYTHONPATH` to include `core_app` before running ETL.

### 1.2 Load Idempotency & Metadata – **Fixed**

**Legacy**:
- Checks row count, `metadata` table (csv_hash, schema_version)
- Skips reload if data is current
- Stores metadata after load

**New**: Now checks `fru_sales_embeddings` row count; skips load if rows > 0 and `--force-refresh-data` not set. (Full metadata table with csv_hash/schema_version not implemented; basic idempotency covers common case.)

### 1.3 wait-for-pgvector – **Fixed**

**Legacy**: `wait-for-pgvector-ready.sh` after `CREATE EXTENSION` before schema init.

**New**: Now waits for pgvector readiness (retries `SELECT 1 FROM (SELECT '[1,2,3]'::vector) t` up to 6 times with 5s delay) before proceeding.

### 1.4 Schema Verification – **Fixed**

**Legacy**: Verifies `fru_sales_embeddings` and `embedding` column exist after init.

**New**: Now verifies `embedding` column exists in `fru_sales_embeddings` after schema init.

---

## 2. Kube API Deployment (api-deployment.yaml)

### 2.1 OPENAI_API_KEY – **Fixed**

**Legacy**: From Secret (e.g. `fru-secrets`) via `valueFrom.secretKeyRef`.

**New**: Now uses `app-credentials` K8s Secret with `OPENAI_API_KEY` from AWS Secrets Manager (via `--openai-secret-arn` in kube_apply). `deploy.py` passes `openai_api_key_secret_arn` from durable outputs.

### 2.2 AWS_BEDROCK_INFERENCE_PROFILE_ID, AWS_BEDROCK_MODEL_ID – **Fixed**

**Legacy** (ConfigMap/deployment): Exported for agent/LLM.

**New**: Now set in `api-deployment.yaml` via kube_apply templating (`--bedrock-inference-profile-id`, `--bedrock-model-id` from deploy.py/.env).

### 2.3 DELTA_TABLE_PATH, DELTA_LAKE_PACKAGE, CONTAINER_TYPE – **Fixed**

**Legacy** (README_WAR_STORIES): Required for scheduler and Spark jobs.

**New**: Now in `api-deployment.yaml`: `DELTA_TABLE_PATH` (s3a://{delta_bucket}/delta/fru_sales), `DELTA_LAKE_PACKAGE`, `CONTAINER_TYPE=eks`, `SPARK_HOME`, passed via kube_apply.

### 2.4 CLOUD_REGION (AWS_REGION for pods) – **Fixed**

**New**: Now templated as `"${AWS_REGION}"` from kube_apply (`--aws-region` from deploy.py/env). Tools use `CLOUD_REGION`; pods receive `AWS_REGION` for AWS SDK.

---

## 3. Nonkube (ECS)

### 3.1 Bedrock & DELTA_LAKE_PACKAGE – **Fixed**

**Legacy** (root_ecs): `AWS_BEDROCK_INFERENCE_PROFILE_ID`, `AWS_BEDROCK_MODEL_ID`, `SPARK_HOME`, `DELTA_LAKE_PACKAGE`.

**New** (nonkube): Now has `AWS_BEDROCK_INFERENCE_PROFILE_ID`, `AWS_BEDROCK_MODEL_ID`, `SPARK_HOME`, `DELTA_LAKE_PACKAGE`, and `DELTA_TABLE_PATH` (s3a://{delta_bucket}/delta/fru_sales). Variables mapped in `terra_var_handling.py`.

### 3.2 PG* and Aurora – **OK**

Nonkube correctly wires PG* from durable and `aurora_from_ecs` SG rule.

---

## 4. ETL Script Path

**Legacy**: `module_app_core/backend/etl/load_openai_embeddings_to_pgvector_rds_api.py`  
**New**: `core_app/backend/etl/load_openai_embeddings_to_pgvector_rds_api.py`

Path is correct; ETL is invoked with `cwd=REPO_ROOT`. ETL uses `backend.etl` so `PYTHONPATH` must include `core_app`. `setup_database.py` runs:

```python
subprocess.run([sys.executable, ETL_SCRIPT], env=env_vars, cwd=REPO_ROOT)
```

`ETL_SCRIPT` is an absolute path; the script is run directly. The ETL imports `backend.utils.env_helpers` – that requires `core_app` on `PYTHONPATH`. **Fixed**: `PYTHONPATH` is now set to `core_app` in `env_vars` before running ETL.

---

## 5. Recommended Fixes (Priority Order)

| # | Fix | File(s) |
|---|-----|---------|
| 1 | Set `FRU_CSV_PATH` in setup_database load_data | `tools/aws/setup_database.py` |
| 2 | Add `PYTHONPATH` for ETL subprocess (include `core_app`) | `tools/aws/setup_database.py` |
| 3 | OPENAI_API_KEY from K8s Secret (not placeholder) | `kube_apply.py`, `api-deployment.yaml` |
| 4 | Add Bedrock, DELTA_*, CONTAINER_TYPE to kube API | `api-deployment.yaml`, `kube_apply.py` |
| 5 | Add Bedrock, DELTA_LAKE_PACKAGE to ECS env_vars | `live_deploy_aws/nonkube/main.tf` |
| 6 | (Optional) Add load idempotency/metadata to setup_database | `tools/aws/setup_database.py` |
| 7 | (Optional) Add wait-for-pgvector before schema init | `tools/aws/setup_database.py` |

---

## 6. Verification Checklist

After fixes (all implemented):

- [x] FRU_CSV_PATH set; PYTHONPATH includes core_app
- [x] Load idempotency (skip if rows exist)
- [x] wait-for-pgvector before schema
- [x] Schema verification (embedding column)
- [x] OPENAI_API_KEY from app-credentials Secret
- [x] Bedrock, DELTA_*, CONTAINER_TYPE in kube API
- [x] CLOUD_REGION / AWS_REGION templated
- [x] Bedrock, DELTA_LAKE_PACKAGE in ECS

Manual verification (requires live deploy):

- [ ] `python tools/aws/setup_database.py --env dev` completes without FileNotFoundError for CSV
- [ ] ETL loads data (check `fru_sales_embeddings` row count)
- [ ] Kube API pods start and `/health` returns 200
- [ ] Kube API `/query` works (semantic search) – requires OPENAI_API_KEY
- [ ] ECS API `/query` works
- [ ] Analytics scheduler (if enabled) runs without DELTA_* errors
