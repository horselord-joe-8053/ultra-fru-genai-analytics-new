# Code Structure by Dimensions

**Cloud:** `aws` | `gcp` | `cloud_shared`  
**Scope:** `kube` | `nonkube` | `scope_shared`  
**Region:** not represented in the directory layout (handled via variables/config)

---

## `tools/`

```
tools/
├── aws/                          # cloud: aws
│   ├── kube/                     # scope: kube
│   ├── nonkube/                  # scope: nonkube
│   └── scope_shared/             # scope: scope_shared
├── gcp/                          # cloud: gcp
└── cloud_shared/                 # cloud: cloud_shared
```

---

## `infra_terraform/`

### `live_deploy/` (cloud → scope)

```
infra_terraform/live_deploy/
├── aws/                          # cloud: aws
│   ├── kube/                     # scope: kube
│   ├── nonkube/                  # scope: nonkube
│   └── scope_shared/             # scope: scope_shared
│       ├── durable/
│       └── nondurable/
└── gcp/                          # cloud: gcp
    ├── kube/
    ├── nonkube/
    └── scope_shared/
        ├── durable/
        └── nondurable/
```

### `modules/` (cloud)

```
infra_terraform/modules/
├── aws/                          # cloud: aws
│   ├── eks/
│   ├── ecs/
│   └── primitives/
├── gcp/                          # cloud: gcp
│   ├── gke/
│   └── primitives/
└── cloud_shared/                 # cloud: cloud_shared
    ├── k8s/
    └── primitives/
```

---

## `core_app/backend/env_utils/`

```
core_app/backend/env_utils/
├── cloud_shared/                 # Interfaces (LLMClient, StorageBackend), provider, credentials
├── aws/                          # cloud: aws (Bedrock, S3, RDS Data API)
├── local/                        # cloud: local (dev)
└── gcp/                          # cloud: gcp (placeholder)
```

---

## Summary Table

| Location | Cloud dimension | Scope dimension |
|----------|-----------------|-----------------|
| `tools/` | `aws/`, `gcp/`, `cloud_shared/` | Under `aws/`: `kube/`, `nonkube/`, `scope_shared/` |
| `infra_terraform/live_deploy/` | `aws/`, `gcp/` | `kube/`, `nonkube/`, `scope_shared/` under each cloud |
| `infra_terraform/modules/` | `aws/`, `gcp/`, `cloud_shared/` | — |
| `core_app/backend/env_utils/` | `cloud_shared/`, `aws/`, `local/`, `gcp/` | — |

---

## 1. Multi-Cloud Suitability (GCP, Oracle)

### Structure evaluation

The current structure is **well-suited** for multi-cloud:

| Aspect | Assessment |
|--------|-------------|
| **Cloud dimension at top level** | `aws/`, `gcp/`, `cloud_shared/` — add `oracle/` as sibling when needed |
| **cloud_shared** | Correct for truly shared assets (K8s manifests, tags, primitives) usable by any cloud |
| **Scope dimension** | `kube`, `nonkube`, `scope_shared` applies to each cloud; GKE/Cloud Run map to kube/nonkube |
| **Region** | Not in path; handled via `CLOUD_REGION`, Terraform vars — works for all clouds |

### Optimal level for Oracle

- Add `tools/oracle/`, `infra_terraform/live_deploy/oracle/`, `infra_terraform/modules/oracle/`, `core_app/backend/env_utils/oracle/` as siblings to AWS/GCP.
- Keep `cloud_shared` for K8s manifests, tags, and any provider-agnostic primitives.
- Do **not** over-abstract: each cloud gets its own concrete modules; avoid premature "cloud-agnostic" abstractions until 2–3 clouds run in production (per War Story 36).

### Recommendation

The structure is **optimal as-is**. Add new clouds by mirroring the AWS layout under each cloud directory. No structural changes needed for GCP or Oracle.

---

## 2. Readiness for GCP (Later Oracle)

### Summary

| Layer | Readiness | Notes |
|-------|-----------|-------|
| **infra_terraform** | ✅ Ready | GCP live_deploy + modules (GKE, GCS, VPC) exist; Terraform layout is parallel |
| **tools** | ❌ Not ready | `tools/gcp/` is empty; orchestrator `handle_gcp` is stub |
| **core_app env_utils** | ⚠️ Partial | LLM factory has placeholders; storage/filesystem is S3-only |
| **core_app runtime** | ⚠️ Partial | DB uses psycopg2 (Cloud SQL OK); agent uses `get_bedrock_client()` |
| **Analytics/Spark** | ❌ Not ready | Delta paths hardcoded `s3a://`; no `gs://` support |

---

### 2.1 infra_terraform — Ready

- `live_deploy/gcp/` has kube, nonkube, scope_shared (durable/nondurable).
- `modules/gcp/` has GKE, primitives (gcs_bucket, vpc).
- Pattern matches AWS; add Oracle stacks when needed.

---

### 2.2 tools — Not ready

| AWS equivalent | GCP needed | Oracle needed |
|----------------|------------|---------------|
| `tools/aws/deploy.py` | `tools/gcp/deploy.py` | `tools/oracle/deploy.py` |
| `tools/aws/teardown.py` | `tools/gcp/teardown.py` | — |
| `tools/aws/kube/` | `tools/gcp/kube/` (GKE apply, kubeconfig) | — |
| `tools/aws/nonkube/` | `tools/gcp/nonkube/` (Cloud Run) | — |
| `tools/aws/scope_shared/` | `tools/gcp/scope_shared/` (Terraform, verify, setup_db) | — |

**Gaps:** `tools/gcp/` is empty. `orchestrator.py` has `handle_gcp()` that prints "GCP provider implementation is pending." Need full mirror of `tools/aws/` structure.

---

### 2.3 core_app env_utils — Partial

| Capability | AWS | GCP equivalent | Oracle equivalent |
|------------|-----|-----------------|-------------------|
| **LLM** | `env_utils/aws/bedrock_client.py` | `env_utils/gcp/gemini_api_client.py` | `env_utils/oracle/genai_client.py` |
| **Object storage** | `env_utils/aws/s3_helpers.py` | `env_utils/gcp/gcs_helpers.py` | `env_utils/oracle/object_storage_helpers.py` |
| **Database** | `env_utils/aws/rds_data_api.py` | Cloud SQL uses psycopg2 (direct) | OCI DB uses oracledb/cx_Oracle |

**LLM:** `client_factory.py` has Priority 3/4 placeholders for Azure/GCP. `LLMClient` ABC exists. Add `GCPGeminiAPIClient` (Google AI Studio) implementing `LLMClient`; extend factory to check `GOOGLE_AI_API_KEY`.

**Storage:** `filesystem.py` has `detect_storage_type()` returning `s3`, `efs`, `local` only. Add `gcs` for `gs://`; add `env_utils/gcp/gcs_helpers.py` with `gcs_exists`, `gcs_listdir`, `gcs_isdir`.

**Database:** RDS Data API is AWS-specific. GCP Cloud SQL and Oracle DB use direct connections (psycopg2, oracledb). App already uses psycopg2 for query path; RDS Data API is for ETL/bootstrap. GCP: use Cloud SQL + psycopg2. Oracle: use OCI DB + oracledb.

---

### 2.4 core_app runtime coupling — Partial

| Issue | Fix |
|-------|-----|
| `app.py` passes `get_bedrock_client()` to `QueryAgent` | Rename to `llm_client`; use `create_llm_client()` instead of `get_bedrock_client()` |
| `QueryAgent` param `bedrock_client` | Rename to `llm_client`; `SQLGeneratorTool` already uses `claude_complete()` (factory) — param is unused |
| `get_bedrock_client()` returns raw boto3 client | Deprecate; agent path should use `LLMClient` interface only |

---

### 2.5 Analytics/Spark — Not ready

| Location | AWS | GCP needed |
|----------|-----|------------|
| `run_analytics.py` | `s3a://` paths | Add `gs://`; derive from `DELTA_TABLE_PATH` or `GCS_DELTA_BUCKET` |
| `bootstrap.py` | `spark.fru.delta_root` default `s3a://example/delta` | Support `gs://` |
| `kube_apply.py`, `deploy_kube.py` | `s3a://{bucket}/delta/fru_sales` | `gs://{bucket}/delta/fru_sales` |
| ECS/nonkube | `DELTA_TABLE_PATH=s3a://...` | `gs://...` |

**Gap:** No `gs://` handling in analytics jobs or deploy tooling. Storage path must be env-driven (e.g. `DELTA_TABLE_PATH` or cloud-specific vars).

---

### 2.6 Effort estimate (GCP fill-in)

| Work item | Effort | Priority |
|-----------|--------|----------|
| `tools/gcp/` mirror (deploy, teardown, kube, nonkube, scope_shared) | High | 1 |
| `env_utils/gcp/gemini_api_client.py` | Medium | 1 |
| `env_utils/gcp/gcs_helpers.py` | Medium | 1 |
| `filesystem.py` add `gcs` + `gs://` | Low | 1 |
| `client_factory.py` add GCP branch | Low | 1 |
| Rename `bedrock_client` → `llm_client` in agent | Low | 2 |
| Analytics jobs `gs://` support | Medium | 2 |
| `orchestrator.py` wire `handle_gcp` | Low | 1 |
