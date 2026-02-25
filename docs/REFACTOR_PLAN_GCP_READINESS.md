# GCP Readiness: Credentials & Refactor Plan

## 1. GCP Credentials for `.env` (Max Access)

### AWS vs GCP analogy

| AWS | GCP equivalent |
|-----|----------------|
| IAM user + access keys | **Service Account** + JSON key file |
| `AWS_PROFILE=admin` + `~/.aws/credentials` | `GOOGLE_APPLICATION_CREDENTIALS` + JSON key path |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | JSON key contains all credentials |

### What to create in GCP Console

1. **Go to:** APIs & Services → Credentials → **Manage service accounts**
2. **Create service account:**
   - Name: e.g. `fru-admin` or `fru-deploy`
   - ID: e.g. `fru-admin`
3. **Assign roles** (for max access, use one of):
   - **Owner** — full project access (simplest, like AWS admin)
   - **Editor** — can create/modify resources but not manage IAM
   - Or granular: `Compute Admin`, `Storage Admin`, `Cloud SQL Admin`, `Kubernetes Engine Admin`, `Service Account User`, etc.
4. **Create key:**
   - Open the service account → Keys → Add Key → Create new key → **JSON**
   - Download the JSON file (keep it secure; never commit)

### `.env` variables

```bash
# =============================================================================
# GCP (max access – equivalent to AWS admin profile + keys)
# =============================================================================
# Project & region
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
# Use CLOUD_REGION for provider-agnostic code; GCP tools can map GCP_REGION -> CLOUD_REGION
CLOUD_REGION=us-central1

# Credentials – Option A: Path to JSON key file (recommended for local dev)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json

# Credentials – Option B: Inline JSON (for CI/containers where file is awkward)
# GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@....iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token",...}
```

### Required APIs (enable in GCP Console)

- **Cloud Storage API** (for GCS / `gs://`)
- **Cloud SQL Admin API** (if using Cloud SQL)
- **Kubernetes Engine API** (for GKE)
- **Artifact Registry API** (for container images; GCP equivalent of ECR)

**Note:** LLM uses **Google AI Studio** (Gemini API) with an API key — no GCP project or Vertex AI API needed for the LLM path. See Section 1.1 below.

### 1.1 LLM: Google AI Studio (Gemini API) — simpler than Vertex AI

For the LLM path, we use **Google AI Studio** with an API key instead of Vertex AI:

- **Simpler:** API key only; no service account or GCP project required for LLM
- **Cheaper:** Free tier for dev; paid pricing comparable to Vertex AI
- **Same models:** Gemini 1.5 Flash/Pro via `google-generativeai` SDK

**Get API key:** [ai.google.dev](https://ai.google.dev) → Get API key → Create

```bash
# LLM (Google AI Studio – separate from infra credentials)
GOOGLE_AI_API_KEY=your-api-key-from-ai-google-dev
# Optional: model override (default: gemini-1.5-flash or gemini-1.5-pro)
# GEMINI_MODEL=gemini-1.5-flash
```

**When to use Vertex AI instead:** See Section 1.2 below.

### 1.2 Optional: Vertex AI (future upgrade path)

Use **Vertex AI** instead of Google AI Studio when you need:

| Trigger | Reason |
|---------|--------|
| **Enterprise compliance** | HIPAA, SOC2, FedRAMP — Vertex AI offers BAA and compliance certifications |
| **VPC-SC** | VPC Service Controls — keep LLM traffic within your private network |
| **Org-level billing** | Centralized GCP billing, quotas, and cost allocation |
| **Workload Identity** | GKE/Cloud Run: use pod/service identity instead of API keys |
| **Model Garden / custom models** | Access to more models, fine-tuned models, or private endpoints |
| **Data residency** | Strict region control (e.g. EU-only) via Vertex AI regional endpoints |

**Implementation:** Add `vertex_ai_client.py` and extend `client_factory` to choose based on env. See **Section 3** (Optional: Vertex AI Implementation).

### Summary

| Env var | Purpose |
|---------|---------|
| `GCP_PROJECT_ID` | GCP project ID (for deploy, GCS, GKE) |
| `GCP_REGION` | GCP region (e.g. `us-central1`) |
| `CLOUD_REGION` | Provider-agnostic; set to same as `GCP_REGION` when using GCP |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Service Account JSON (for deploy, GCS, GKE) |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | (Optional) Inline JSON for CI/containers |
| `GOOGLE_AI_API_KEY` | Gemini API key from ai.google.dev (for LLM only) |
| `GCP_LLM_USE_VERTEX_AI` | (Optional) Set to `true` to use Vertex AI instead of Gemini API; requires `GOOGLE_APPLICATION_CREDENTIALS` |

---

## 2. Refactor Plan for GCP Readiness

### Overview

Four areas need work. Dependencies and recommended order:

```
Phase 0: Foundation (env_utils + runtime decoupling)
   ↓
Phase 1: core_app env_utils (LLM, storage)
   ↓
Phase 2: core_app runtime (agent llm_client)
   ↓
Phase 3: Analytics/Spark (gs:// support)
   ↓
Phase 4: tools/gcp (deploy, teardown, kube, scope_shared)
   ↓
Phase 5: Orchestrator wiring
```

---

### Phase 0: Foundation (prerequisite)

**Goal:** Establish GCP env vars and provider detection so later phases can branch on cloud.

| Task | Description | Effort |
|------|-------------|--------|
| 0.1 | Update `.env.example` with GCP vars (see Section 1) | Low |
| 0.2 | Add `CLOUD_PROVIDER` or detect from env: `CLOUD_PROVIDER=aws|gcp` (or infer: `GCP_PROJECT_ID` set → gcp) | Low |
| 0.3 | Add `tools/cloud_shared/env.py` helper: `get_cloud_provider() -> str` | Low |

**Deliverable:** Code can branch on `cloud_provider == "gcp"` without breaking AWS.

---

### Phase 1: core_app env_utils (LLM + storage)

**Goal:** Add GCP equivalents for LLM and object storage so the app can run on GCP.

#### 1.1 LLM – Google AI Studio (Gemini API) client

| Task | Description | Effort |
|------|-------------|--------|
| 1.1.1 | Create `core_app/backend/env_utils/gcp/__init__.py` | Low |
| 1.1.2 | Create `core_app/backend/env_utils/gcp/gemini_api_client.py` implementing `LLMClient` | Medium |
| | - Use `google-generativeai` SDK (Gemini API) | |
| | - Env: `GOOGLE_AI_API_KEY` (from ai.google.dev) | |
| | - Optional: `GEMINI_MODEL` (default: `gemini-1.5-flash` or `gemini-1.5-pro`) | |
| | - Implement `complete()` and `stream_complete()` | |
| 1.1.3 | Extend `client_factory.py`: add Priority 3 branch for GCP | Low |
| | - Check `GOOGLE_AI_API_KEY` | |
| | - Import and return `GCPGeminiAPIClient()` | |
| | - Design for optional Vertex AI: check `GCP_LLM_USE_VERTEX_AI` first (see Section 3) | |
| 1.1.4 | Add `requirements.txt`: `google-generativeai` | Low |

#### 1.2 Storage – GCS helpers

| Task | Description | Effort |
|------|-------------|--------|
| 1.2.1 | Create `core_app/backend/env_utils/gcp/gcs_helpers.py` | Medium |
| | - `gcs_exists(gs_path: str) -> bool` | |
| | - `gcs_listdir(gs_path: str) -> List[str]` | |
| | - `gcs_isdir(gs_path: str) -> bool` | |
| | - Parse `gs://bucket/key` with `urllib.parse` | |
| | - Use `google-cloud-storage` client | |
| 1.2.2 | Extend `filesystem.py` `detect_storage_type()`: add `gs://` → `'gcs'` | Low |
| 1.2.3 | Extend `filesystem.py` `exists()`, `listdir()`, `isdir()`: branch on `gcs`, call `gcs_*` | Low |
| 1.2.4 | Add `requirements.txt`: `google-cloud-storage` | Low |

**Deliverable:** App can use Gemini API (Google AI Studio) for LLM and GCS for file operations when `CLOUD_PROVIDER=gcp`.

---

### Phase 2: core_app runtime (agent llm_client)

**Goal:** Remove AWS-specific `get_bedrock_client()` from agent path; use `LLMClient` interface only.

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Rename `QueryAgent.__init__(bedrock_client, ...)` → `llm_client` | Low |
| 2.2 | Rename `SQLGeneratorTool.__init__(bedrock_client, ...)` → `llm_client` | Low |
| | - SQLGeneratorTool uses `claude_complete()` (factory); param is unused — can pass `None` or remove | |
| 2.3 | In `app.py`: replace `get_bedrock_client()` with `create_llm_client()` for QueryAgent | Low |
| | - Pass `llm_client=create_llm_client()` | |
| 2.4 | Deprecate or remove `get_bedrock_client()` from agent path | Low |
| | - Keep for backward compat if other code uses it; add deprecation warning | |
| 2.5 | Audit: any other `get_bedrock_client()` callers → switch to `create_llm_client()` | Low |

**Deliverable:** Agent is cloud-agnostic; works with AWS Bedrock or GCP Gemini API via factory.

---

### Phase 3: Analytics/Spark (gs:// support)

**Goal:** Delta Lake and analytics jobs work with `gs://` paths on GCP.

#### 3.1 Path abstraction

| Task | Description | Effort |
|------|-------------|--------|
| 3.1.1 | Create `core_app/analytics/jobs/utils/storage_paths.py` (or extend existing) | Low |
| | - `to_spark_path(path: str) -> str`: `s3://` → `s3a://`, `gs://` stays `gs://` (Spark supports both) | |
| | - `derive_csv_path_from_delta(delta_path: str) -> str`: handle `s3a://` and `gs://` | |
| 3.1.2 | Update `run_analytics.py`: use shared path helpers; support `gs://` in CSV/Delta paths | Medium |
| 3.1.3 | Update `bootstrap.py`: `spark.fru.delta_root` default or env; support `gs://` | Low |
| 3.1.4 | Add Spark GCS connector: `gcs-connector` JAR or `spark.hadoop.fs.gs.impl` config | Medium |
| | - GKE/Cloud Run: use Workload Identity or service account; Spark reads `GOOGLE_APPLICATION_CREDENTIALS` | |

#### 3.2 Deploy tooling

| Task | Description | Effort |
|------|-------------|--------|
| 3.2.1 | Make `DELTA_TABLE_PATH` cloud-agnostic: `s3a://...` or `gs://...` from env | Low |
| 3.2.2 | GCP kube/nonkube: set `DELTA_TABLE_PATH=gs://{bucket}/delta/fru_sales` from Terraform output | Low |
| 3.2.3 | Ensure Spark image has GCS connector when `CLOUD_PROVIDER=gcp` | Medium |
| | - May need separate Spark Dockerfile or build-arg for GCP | |

**Deliverable:** Analytics jobs run on GCP with `gs://` Delta paths.

---

### Phase 4: tools/gcp (deploy, teardown, scope_shared)

**Goal:** Mirror `tools/aws/` structure so GCP deploy/teardown/verify work.

#### 4.1 Directory structure

```
tools/gcp/
├── deploy.py              # Entry point (like tools/aws/deploy.py)
├── teardown.py            # Teardown orchestrator
├── kube/
│   ├── deploy_kube.py     # GKE deploy: apply K8s, kubeconfig, CronJob
│   ├── kube_apply.py      # kubectl apply manifests (reuse cloud_shared/k8s with GKE context)
│   └── gke_kubeconfig.py  # gcloud container clusters get-credentials
├── nonkube/
│   └── deploy_nonkube.py  # Cloud Run deploy (if applicable)
└── scope_shared/
    ├── core/
    │   ├── backend.py     # GCP-specific: state in GCS, project/region resolution
    │   └── terra_runner.py
    ├── deploy/
    │   ├── build_and_push_images.py  # Artifact Registry (not ECR)
    │   ├── setup_database.py        # Cloud SQL setup
    │   └── ...
    └── verify/
        └── verify_all_deploy.py
```

#### 4.2 Key differences from AWS

| AWS | GCP |
|-----|-----|
| ECR | Artifact Registry |
| S3 state bucket | GCS bucket for Terraform state |
| boto3 / AWS CLI | google-cloud-* SDKs / gcloud CLI |
| EKS kubeconfig | `gcloud container clusters get-credentials` |
| Secrets Manager | Secret Manager |
| RDS Data API | Cloud SQL + psycopg2 |

#### 4.3 Implementation order

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | Create `tools/gcp/scope_shared/core/backend.py` | High |
| | - `resolve_region()`: use `GCP_REGION` or `CLOUD_REGION` | |
| | - `gcs_state_bucket()`: GCS bucket for Terraform state (like `resolve_state_bucket` for S3) | |
| | - `stack_id_from_dir()`: reuse logic; cloud=`gcp` | |
| 4.2 | Create `tools/gcp/scope_shared/core/terra_runner.py` | Medium |
| | - `get_terra_env()`: set `GOOGLE_APPLICATION_CREDENTIALS`, `CLOUD_REGION` | |
| 4.3 | Create `tools/gcp/scope_shared/deploy/build_and_push_images.py` | High |
| | - Use `gcloud artifacts docker` (Artifact Registry) | |
| | - Build context: same as AWS (core_app) | |
| 4.4 | Create `tools/gcp/scope_shared/deploy/setup_database.py` | Medium |
| | - Cloud SQL: use psycopg2 (no RDS Data API) | |
| | - Ensure pgvector, schema, load data | |
| 4.5 | Create `tools/gcp/kube/deploy_kube.py` | High |
| | - Get GKE kubeconfig | |
| | - Apply cloud_shared K8s manifests | |
| | - Set `DELTA_TABLE_PATH=gs://...` in ConfigMap | |
| 4.6 | Create `tools/gcp/kube/kube_apply.py` | Medium |
| | - Similar to AWS; use GKE context | |
| 4.7 | Create `tools/gcp/deploy.py` | High |
| | - Phases: doctor → durable → nondurable → build/push → kube/nonkube | |
| | - Mirror `tools/aws/deploy.py` flow | |
| 4.8 | Create `tools/gcp/teardown.py` | High |
| | - Reverse order: kube/nonkube → nondurable → durable | |
| 4.9 | Create `tools/gcp/scope_shared/verify/verify_all_deploy.py` | Medium |
| | - Health check, query test (use `create_llm_client()` — Gemini API or Vertex AI per env) | |
| 4.10 | Create `tools/gcp/standalone/doctor.py` (optional) | Low |
| | - Check gcloud, GCP_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS | |

**Deliverable:** `python tools/gcp/deploy.py --scope kube --env dev` deploys to GKE.

---

### Phase 5: Orchestrator wiring

| Task | Description | Effort |
|------|-------------|--------|
| 5.1 | Implement `handle_gcp()` in `orchestrator.py` | Low |
| | - Route `deploy` → `python tools/gcp/deploy.py` | |
| | - Route `teardown` → `python tools/gcp/teardown.py` | |
| | - Route `doctor` → `python tools/gcp/standalone/doctor.py` | |
| | - Route `verify` → `python tools/gcp/scope_shared/verify/verify_all_deploy.py` | |
| 5.2 | Pass `--env`, `--scope`, `--region` to GCP scripts | Low |

**Deliverable:** `orchestrator.py deploy --provider gcp --scope kube --env dev` works.

---

### Phase summary table

| Phase | Focus | Effort | Dependencies |
|-------|-------|--------|--------------|
| 0 | Foundation (provider detection, .env) | Low | None |
| 1 | env_utils (Gemini API, GCS) | Medium | Phase 0 |
| 2 | Agent llm_client decoupling | Low | Phase 1 (optional) |
| 3 | Analytics gs:// support | Medium | Phase 0 |
| 4 | tools/gcp full mirror | High | Phases 1, 3 |
| 5 | Orchestrator handle_gcp | Low | Phase 4 |

---

### Suggested execution order

1. **Phase 0** — Quick win; unblocks everything.
2. **Phase 1** — Enables GCP LLM + storage in core_app.
3. **Phase 2** — Clean up agent; can run in parallel with Phase 3.
4. **Phase 3** — Enables analytics on GCP.
5. **Phase 4** — Largest; implement in sub-phases (scope_shared first, then kube, then deploy/teardown).
6. **Phase 5** — Final wiring.
7. **Section 3 (optional)** — Add Vertex AI client when compliance or VPC-SC is required.

---

### Risk and mitigation

| Risk | Mitigation |
|------|------------|
| GCP Terraform state backend differs from AWS | Document GCS backend config; ensure `backend_config()` in tools supports GCS |
| Gemini API differs from Bedrock | Keep `LLMClient` interface; encapsulate differences in `GCPGeminiAPIClient` |
| Vertex AI API differs from Gemini API | Same `LLMClient` interface; encapsulate in `GCPVertexAIClient` (Section 3) |
| Spark GCS connector version/compat | Pin `gcs-connector-hadoop3` version; test with Delta 4.x |
| tools/gcp drift from tools/aws | Use tools/aws as reference; extract shared patterns to `tools/cloud_shared` where appropriate |

---

## 3. Optional: Vertex AI Implementation

When you need Vertex AI instead of Google AI Studio (see Section 1.2), add this optional phase.

### 3.1 When to implement

- After Phase 1 is complete (Gemini API client exists).
- When compliance, VPC-SC, or Workload Identity requirements arise.

### 3.2 Implementation tasks

| Task | Description | Effort |
|------|-------------|--------|
| 3.2.1 | Enable **Vertex AI API** in GCP Console | Low |
| 3.2.2 | Add Service Account role: **Vertex AI User** (if not using Owner/Editor) | Low |
| 3.2.3 | Create `core_app/backend/env_utils/gcp/vertex_ai_client.py` implementing `LLMClient` | Medium |
| | - Use `google-cloud-aiplatform` (Vertex AI Generative AI) | |
| | - Env: `GCP_PROJECT_ID`, `GCP_REGION`, `GOOGLE_APPLICATION_CREDENTIALS` | |
| | - Optional: `GCP_VERTEX_MODEL` (e.g. `gemini-1.5-flash-001`) | |
| | - Implement `complete()` and `stream_complete()` | |
| 3.2.4 | Extend `client_factory.py`: add GCP branch that checks `GCP_LLM_USE_VERTEX_AI` | Low |
| | - If `GCP_LLM_USE_VERTEX_AI=true` and `GOOGLE_APPLICATION_CREDENTIALS` set → `GCPVertexAIClient()` | |
| | - Else if `GOOGLE_AI_API_KEY` set → `GCPGeminiAPIClient()` (existing) | |
| 3.2.5 | Add `requirements.txt`: `google-cloud-aiplatform` | Low |
| 3.2.6 | Update `tools/gcp/scope_shared/verify/verify_all_deploy.py` | Low |
| | - Use factory (already cloud-agnostic); no change if factory returns Vertex client | |

### 3.3 Client factory selection logic (GCP)

```
GCP LLM branch (Priority 3):
  if GCP_LLM_USE_VERTEX_AI == "true" and GOOGLE_APPLICATION_CREDENTIALS set:
    → GCPVertexAIClient (Vertex AI)
  elif GOOGLE_AI_API_KEY set:
    → GCPGeminiAPIClient (Google AI Studio)
  else:
    → skip (try next provider)
```

### 3.4 Env vars for Vertex AI

```bash
# Use Vertex AI instead of Gemini API
GCP_LLM_USE_VERTEX_AI=true
GCP_PROJECT_ID=your-project
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
# Optional model override
# GCP_VERTEX_MODEL=gemini-1.5-flash-001
```

### 3.5 Coexistence

Both clients implement `LLMClient`; the factory chooses one at runtime. No code changes elsewhere — agent, tools, and verify scripts use `create_llm_client()` and remain unaware of which backend is used.
