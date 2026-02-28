# GCP Readiness: Credentials & Refactor Plan

**See also:** [docs/GCP_AWS_REFERENCE.md](GCP_AWS_REFERENCE.md) — comprehensive GCP ↔ AWS mapping for all four areas (env_utils, modules, live_deploy, tools).

## 1. GCP Credentials for `.env` (Max Access)

### AWS vs GCP analogy

| AWS | GCP equivalent |
|-----|----------------|
| IAM user + access keys | **Service Account** + JSON key file |
| `AWS_PROFILE=admin` + `~/.aws/credentials` | `GOOGLE_APPLICATION_CREDENTIALS` + JSON key path |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | JSON key contains all credentials |

### What to create in GCP Console

> **⚠️ 1.1 Service account is project-specific (not cross-project):** Service accounts belong to a single GCP project. Watch which project you are under when creating the service account. Use the project selector at the top of the GCP Console to ensure you're in the correct project before creating credentials.

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

Enable these in **APIs & Services → Library** (search by name). Ensure you're in the correct project.

| API | Purpose | Notes |
|-----|---------|-------|
| **Cloud Storage API** | GCS / `gs://` paths | There is also "Cloud Storage" — both "Cloud Storage" and "Cloud Storage API" may appear; both are typically already enabled for many projects. Use **Cloud Storage API** for programmatic access. |
| **Cloud SQL Admin API** | Cloud SQL | **Needs to be enabled** if using Cloud SQL. |
| **Kubernetes Engine API** | GKE | **Needs to be enabled.** Enablement can take a few minutes to propagate. |
| **Artifact Registry API** | Container images (GCP equivalent of ECR) | **Needs to be enabled** for pushing Docker images. |

**Note:** LLM uses **Google AI Studio** (Gemini API) with an API key — no GCP project or Vertex AI API needed for the LLM path. See Section 1.1 below.

### 1.1 LLM: Google AI Studio (Gemini API) — simpler than Vertex AI

**Strategy:** Start with **Google AI Studio** (API key) first. Optionally upgrade to **Vertex AI** later when enterprise compliance, VPC-SC, or Workload Identity is required.

For the LLM path, we use **Google AI Studio** with an API key instead of Vertex AI:

- **Simpler:** API key only; no service account or GCP project required for LLM
- **Cheaper:** Free tier for dev; paid pricing comparable to Vertex AI
- **Same models:** Gemini 1.5 Flash/Pro via unified `google-genai` SDK

#### 1.1.1 Detailed setup: Google AI Studio (API key) — as of Feb 2026

1. **Access Google AI Studio**
   - Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (or [ai.google.dev](https://ai.google.dev) → Get API key)
   - Sign in with your Google account

2. **Create API key**
   - Click **"Get API keys"** or **"Create API key"**
   - Choose to create the key in an **existing project** or a **new project**
   - Each API key is associated with a Google Cloud project; new users may get a default project after accepting Terms of Service

3. **Copy and secure the key**
   - Click **Copy** to save the API key
   - Never commit it to version control; use `.env` (gitignored) or a secrets manager

4. **Environment variable**
   - Official [python-genai](https://github.com/googleapis/python-genai) accepts `GEMINI_API_KEY` or `GOOGLE_API_KEY` (latter takes precedence)
   - We use `GOOGLE_AI_API_KEY` in our `.env`; our client will check `GOOGLE_AI_API_KEY` first, then `GEMINI_API_KEY`, then `GOOGLE_API_KEY` for SDK compatibility

```bash
# LLM (Google AI Studio – separate from infra credentials)
GOOGLE_AI_API_KEY=your-api-key-from-ai-google-dev
# Or use SDK-native: GEMINI_API_KEY / GOOGLE_API_KEY
# Optional: model override (default: gemini-1.5-flash or gemini-2.5-flash)
# GEMINI_MODEL=gemini-1.5-flash
```

**Limitations (Google AI Studio):** Max 100 API keys and 50 projects visible; 10 projects at a time. For advanced management, use Google Cloud Console.

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

#### 1.2.1 Detailed setup: Vertex AI — as of Feb 2026

Vertex AI requires more setup than Google AI Studio. Follow these steps when upgrading:

1. **Prerequisites**
   - GCP project with billing enabled
   - Service account with JSON key (see Section 1 above)
   - `GOOGLE_APPLICATION_CREDENTIALS` set to the JSON key path

2. **Enable Vertex AI API**
   - Go to [APIs & Services → Library](https://console.cloud.google.com/apis/library)
   - Search for **Vertex AI API**
   - Click **Enable**

3. **Grant Service Account role**
   - IAM & Admin → IAM → find your service account
   - Add role: **Vertex AI User** (or use Owner/Editor for max access)

4. **Region**
   - Vertex AI is regional; choose a [supported region](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations) (e.g. `us-central1`)

5. **Migration from Google AI Studio**
   - Per [Google's migration guide](https://cloud.google.com/vertex-ai/generative-ai/docs/migrate/migrate-google-ai): endpoints differ (`aiplatform.googleapis.com` vs `generativelanguage.googleapis.com`), auth differs (service account vs API key)
   - Use the **unified `google-genai` SDK** with `vertexai=True` — same SDK, different client config
   - Delete unused API keys from Google AI Studio after migration (security best practice)

**Implementation:** Add `vertex_ai_client.py` and extend GCP's `get_llm_client()` to choose based on env. See **Section 3** (Optional: Vertex AI Implementation).

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

### 1.3 Crash Course: Service Account Keys vs Workload Identity

When you create a service account key in GCP Console (IAM & Admin → Service accounts → Keys), you see this warning:

> **Service account keys could pose a security risk if compromised. We recommend you avoid downloading service account keys and instead use the Workload Identity Federation.**

This section explains what that means and when to use each approach for this project.

#### 1.3.1 Why Google warns about service account keys

A **service account key** is a JSON file containing a private key. Anyone with that file can authenticate as the service account. Per [Best practices for managing service account keys](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys):

- **Credential leakage:** Keys can end up in public repos, backups, or email—and then work immediately (no 2FA like user accounts).
- **Privilege escalation:** A compromised key grants full access to whatever the service account can do.
- **Non-repudiation:** Actions taken with a key can't be tied to a specific person.

Google's recommended order (most → least secure): [Choose the right authentication method](https://cloud.google.com/docs/authentication#choose-the-right-authentication-method-for-your-use-case)

1. **Attach a service account to the resource** (GCE VM, Cloud Run, etc.) — no key file.
2. **Workload Identity Federation for GKE** — for pods in GKE; no key file.
3. **Workload Identity Federation** — for workloads outside GCP (e.g. GitHub Actions, AWS); no key file.
4. **Service account key** — last resort when none of the above apply.

#### 1.3.2 Two different "Workload Identity" concepts

| Term | Scope | Purpose |
|------|-------|---------|
| **Workload Identity Federation for GKE** | GKE clusters only | Pods in GKE get short-lived tokens via a metadata server. No JSON keys. GCP manages the pool automatically. |
| **Workload Identity Federation** (general) | Workloads outside GCP | GitHub, AWS, Azure, etc. exchange their tokens for temporary GCP access. No JSON keys. Requires identity provider setup. |

For this project, **Workload Identity Federation for GKE** is the relevant one when we deploy to GKE. The console warning links to the general concept; for GKE, the practical doc is [Authenticate to Google Cloud APIs from GKE workloads](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity).

#### 1.3.3 How Workload Identity Federation for GKE works

When enabled on a GKE cluster ([About Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)):

1. GKE creates a workload identity pool: `PROJECT_ID.svc.id.goog`
2. GKE deploys a **metadata server** on each node that intercepts credential requests
3. A pod requests a token → metadata server asks the K8s API for a Kubernetes ServiceAccount token → exchanges it for a short-lived GCP access token
4. Your code uses **Application Default Credentials (ADC)** — no changes needed. The Google Cloud client libraries automatically use the metadata server.

**No JSON key file is stored or mounted.** Tokens are short-lived (default 1 hour) and refreshed automatically.

#### 1.3.4 When to use what (for this project)

| Environment | Recommended auth | JSON key? |
|-------------|------------------|-----------|
| **Local dev** | `gcloud auth application-default login` (user creds) or JSON key | Optional; key only if user creds don't work |
| **GKE (production)** | Workload Identity Federation for GKE | **No** — link K8s ServiceAccount to GCP Service Account |
| **Cloud Run** | Attach service account to the service | **No** |
| **GCE VM** | Attach service account to the VM | **No** |
| **CI outside GCP** (e.g. GitHub Actions) | Workload Identity Federation (GitHub as provider) | **No** |
| **Legacy / no-WIF setup** | JSON key in Secret or env | Yes (last resort) |

#### 1.3.5 GKE Workload Identity setup (concise steps)

For **AI implementing the refactor**, when deploying to GKE, configure Workload Identity instead of mounting a JSON key. Reference: [Authenticate to Google Cloud APIs from GKE workloads](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity).

**Prerequisites:** Enable [IAM Service Account Credentials API](https://console.cloud.google.com/apis/api/iamcredentials.googleapis.com/overview). Need `roles/iam.serviceAccountAdmin` and `roles/container.admin`.

**Step 1 — Enable on cluster (Standard GKE):**
```bash
gcloud container clusters update CLUSTER_NAME --location=LOCATION --workload-pool=PROJECT_ID.svc.id.goog
```
*(Autopilot: Workload Identity is always enabled.)*

**Step 2 — Enable on node pool (Standard only):**
```bash
gcloud container node-pools update NODEPOOL_NAME --cluster=CLUSTER_NAME --location=LOCATION --workload-metadata=GKE_METADATA
```

**Step 3 — Link K8s ServiceAccount to GCP Service Account:**
```bash
# Create K8s SA
kubectl create serviceaccount KSA_NAME --namespace NAMESPACE

# Create GCP SA (or use existing, e.g. fru-proj-1-admin)
gcloud iam service-accounts create GSA_NAME --project=PROJECT_ID

# Grant GCP SA the roles it needs (e.g. Vertex AI User)
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:GSA_NAME@PROJECT_ID.iam.gserviceaccount.com" --role="roles/aiplatform.user"

# Allow K8s SA to impersonate GCP SA
gcloud iam service-accounts add-iam-policy-binding GSA_NAME@PROJECT_ID.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:PROJECT_ID.svc.id.goog[NAMESPACE/KSA_NAME]"

# Annotate K8s SA
kubectl annotate serviceaccount KSA_NAME --namespace NAMESPACE \
  iam.gke.io/gcp-service-account=GSA_NAME@PROJECT_ID.iam.gserviceaccount.com
```

**Step 4 — Use the K8s SA in your Pod/Deployment:**
```yaml
spec:
  serviceAccountName: KSA_NAME
```

**Step 5 (Standard only):** Ensure pods run on nodes with the metadata server:
```yaml
spec:
  nodeSelector:
    iam.gke.io/gke-metadata-server-enabled: "true"
```

**Code:** No changes. Use `genai.Client(vertexai=True, project=..., location=...)`; ADC picks up credentials from the metadata server automatically.

#### 1.3.6 References

| Topic | URL |
|-------|-----|
| Best practices for service account keys | [cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys) |
| Choose authentication method | [cloud.google.com/docs/authentication](https://cloud.google.com/docs/authentication) |
| Workload Identity Federation for GKE (concepts) | [cloud.google.com/kubernetes-engine/docs/concepts/workload-identity](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity) |
| GKE Workload Identity how-to | [cloud.google.com/kubernetes-engine/docs/how-to/workload-identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) |
| Workload Identity Federation (general, for non-GCP) | [cloud.google.com/iam/docs/workload-identity-federation](https://cloud.google.com/iam/docs/workload-identity-federation) |

---

## 2. Refactor Plan for GCP Readiness

### Overview

**LLM strategy:** Start with **Google AI Studio** (API key) first. Optionally upgrade to **Vertex AI** when enterprise requirements arise. Both use the **unified `google-genai` SDK** — one SDK, different client initialization. See [War Story: Unified Google Gen AI SDK](#war-story-unified-google-gen-ai-sdk) for lessons learned.

#### 2.0 Option A: Provider-driven LLM factory (agreed architecture)

Each provider owns its LLM facilities; the factory lives in shared code and dispatches by provider.

| Provider | Module | `get_llm_client()` returns |
|----------|--------|---------------------------|
| **local** | `env_utils/local/` | `LocalClaudeClient` if `CLAUDE_API_KEY` set, else `None` |
| **aws** | `env_utils/aws/` | `AWSBedrockClient` if Bedrock config present, else `None` |
| **gcp** | `env_utils/gcp/` | `GCPGeminiAPIClient` or `GCPVertexAIClient` if GCP LLM config present, else `None` |

**Factory location:** `env_utils/cloud_shared/client_factory.py` (moved from `llm/client_factory.py`)

**Factory logic (cloud-first):**
1. **If `CLOUD_PROVIDER` is set** → call *only* that provider's `get_llm_client()`. If it returns `None` (e.g. GCP chosen but no `GOOGLE_AI_API_KEY`), raise `ValueError`. We do *not* try other providers — this avoids silently using the wrong LLM when you explicitly chose a provider (e.g. `CLOUD_PROVIDER=gcp` but GCP creds missing → fail fast, don't fall back to AWS Bedrock).
2. **If `CLOUD_PROVIDER` is unset** → fallback to priority order: **aws → gcp → local**. Cloud deployments take precedence; local is last when config is ambiguous (e.g. AWS EKS/GCP GKE with Bedrock/Gemini wins over `CLAUDE_API_KEY`).
3. If no client found → raise `ValueError` with helpful message.

**Imports:** All callers import directly from `backend.env_utils.cloud_shared.client_factory` (no re-export in `backend.llm`).

**SDK choice (as of Feb 2026):**
- `google-generativeai` — **deprecated** (Nov 30, 2025); limited to critical bug fixes
- `vertexai.generative_models` (google-cloud-aiplatform) — **deprecated**; removed after June 24, 2026
- **`google-genai`** — **recommended**; [official repo](https://github.com/googleapis/python-genai); supports both Gemini Developer API (AI Studio) and Vertex AI

Per [Vertex AI SDK migration guide](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations/genai-vertexai-sdk): migrate to `google-genai` for both paths.

**Authentication summary (official [python-genai](https://github.com/googleapis/python-genai)):**

| Backend | Auth method | Env vars (optional) | Code pattern |
|---------|-------------|---------------------|--------------|
| **AI Studio** | API key | `GEMINI_API_KEY` or `GOOGLE_API_KEY` (latter takes precedence) | `genai.Client(api_key='...')` or `genai.Client()` |
| **Vertex AI** | Service account / ADC | `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | `genai.Client(vertexai=True, project='...', location='...')` or `genai.Client()` |
| **Vertex AI (org-restricted)** | Explicit credentials | `GOOGLE_APPLICATION_CREDENTIALS` + JSON key path | Load credentials with `google-auth`; pass `credentials=creds` |

**VM/container auth:** See [Section 2.1.1](#211-authentication-in-vms-and-containers) for automatic auth in GKE/Cloud Run/VMs.

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
| 0.2 | Add `CLOUD_PROVIDER` or detect from env: `CLOUD_PROVIDER=aws` or `gcp` (or infer: `GCP_PROJECT_ID` set → gcp) | Low |
| 0.3 | Ensure `core_app/backend/env_utils/cloud_shared/provider.py` has `get_cloud_provider() -> str` | Low |
| | - Already exists; used by credentials, storage, health. Factory will use it. | |

**Deliverable:** Code can branch on `cloud_provider == "gcp"` without breaking AWS.

---

### Phase 1: core_app env_utils (LLM + storage)

**Goal:** Add GCP equivalents for LLM and object storage so the app can run on GCP.

#### 2.1.1 Authentication in VMs and containers

**Yes — workloads in GCP VMs or containers can authenticate automatically**, including recovery from token expiration.

| Environment | Vertex AI auth | Auto-refresh? |
|-------------|----------------|---------------|
| **GKE (Workload Identity)** | Pod's K8s SA → GCP SA via metadata server. No JSON key. | Yes — tokens fetched on demand, cached, auto-refreshed |
| **Cloud Run** | Service identity. No JSON key. | Yes |
| **GCE VM** | VM's attached service account via metadata. No JSON key. | Yes |
| **Container with JSON key** | `GOOGLE_APPLICATION_CREDENTIALS` → JSON file. SDK uses private key to sign JWTs. | Yes — private key never expires; SDK refreshes short-lived JWTs automatically |
| **AI Studio (API key)** | API key in env/secret. Keys don't expire until revoked. | N/A — key is long-lived |

**Takeaway:** For Vertex AI on GKE/Cloud Run/GCE, use **Workload Identity** or the VM's service account — no JSON keys, no manual refresh. For containers outside GCP or when Workload Identity isn't set up, use `GOOGLE_APPLICATION_CREDENTIALS`; the `google-genai` SDK (via `google-auth`) automatically refreshes tokens. See [Section 1.3 Crash Course](#13-crash-course-service-account-keys-vs-workload-identity) for setup steps.

#### 1.1 LLM – Google AI Studio first, Vertex AI upgrade path

**Use the unified `google-genai` SDK** for both paths. Same package, different client initialization. Code after client creation is identical.

**Precise client initialization (from [python-genai](https://github.com/googleapis/python-genai)):**

```python
# AI Studio (api_key)
from google import genai
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
# Or: client = genai.Client()  # picks up GEMINI_API_KEY/GOOGLE_API_KEY from env

# Vertex AI (ADC / GOOGLE_APPLICATION_CREDENTIALS)
client = genai.Client(
    vertexai=True,
    project=os.environ["GCP_PROJECT_ID"],
    location=os.environ["GCP_REGION"],
)
# SDK uses Application Default Credentials (env GOOGLE_APPLICATION_CREDENTIALS or metadata)

# Vertex AI (explicit credentials — for orgs that restrict ADC)
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(
    key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = genai.Client(vertexai=True, project=..., location=..., credentials=creds)
```

**API usage (identical for both backends):**

```python
# Non-streaming
response = client.models.generate_content(
    model="gemini-2.5-flash",  # or gemini-1.5-flash
    contents="Why is the sky blue?",
    config=types.GenerateContentConfig(system_instruction="...", max_output_tokens=2000),
)
text = response.text

# Streaming
for chunk in client.models.generate_content_stream(model="...", contents="..."):
    print(chunk.text, end="")
```

| Task | Description | Effort |
|------|-------------|--------|
| 1.1.1 | Create `core_app/backend/env_utils/gcp/__init__.py` | Low |
| 1.1.2 | Create `core_app/backend/env_utils/gcp/gemini_api_client.py` implementing `LLMClient` | Medium |
| | - Use **`google-genai`** (`pip install google-genai`) | |
| | - **AI Studio:** `genai.Client(api_key=...)` or `genai.Client()` with `GEMINI_API_KEY`/`GOOGLE_API_KEY` | |
| | - Env: `GOOGLE_AI_API_KEY` or `GEMINI_API_KEY` (we use `GOOGLE_AI_API_KEY` for consistency with our `.env`) | |
| | - Optional: `GEMINI_MODEL` (default: `gemini-1.5-flash` or `gemini-2.5-flash`) | |
| | - `complete()` → `client.models.generate_content()`; `stream_complete()` → `client.models.generate_content_stream()` | |
| | - Map response to `LLMClient` shape: `{text: response.text, tokens: {...}}` | |
| 1.1.3 | Add `get_llm_client() -> Optional[LLMClient]` to each provider | Low |
| | - **local:** `env_utils/local/` — if `CLAUDE_API_KEY` set → `LocalClaudeClient()`, else `None` | |
| | - **aws:** `env_utils/aws/` — if Bedrock config → `AWSBedrockClient()`, else `None` | |
| | - **gcp:** `env_utils/gcp/` — if `GCP_LLM_USE_VERTEX_AI` + creds → Vertex client; elif `GOOGLE_AI_API_KEY` → `GCPGeminiAPIClient()`; else `None` | |
| 1.1.4 | **Move factory** from `llm/client_factory.py` → `env_utils/cloud_shared/client_factory.py` | Low |
| | - Use `get_cloud_provider()`; if set, call provider's `get_llm_client()`; else fallback to aws → gcp → local (cloud-first) | |
| | - Update all imports to `backend.env_utils.cloud_shared.client_factory`: `app.py`, `query_agent.py`, `sql_generator_tool.py`, `llm/__init__.py` | |
| 1.1.5 | Add `requirements.txt`: **`google-genai`** (and `google-auth` if using explicit credentials) | Low |

**Vertex AI upgrade (Section 3):** Add `vertex_ai_client.py` with `genai.Client(vertexai=True, project=..., location=...)`. SDK uses ADC when `GOOGLE_APPLICATION_CREDENTIALS` is set; for org-restricted setups, load credentials explicitly with `google-auth`.

#### 1.1.6 Big code changes: Google Studio first → Vertex AI upgrade

| Phase | What changes | Effort |
|-------|--------------|--------|
| **Phase 1a: Google AI Studio** | Add `gemini_api_client.py`; add `get_llm_client()` to gcp; move factory to cloud_shared. GCP's `get_llm_client()` returns `GCPGeminiAPIClient()` when `GOOGLE_AI_API_KEY` set. Agent, `claude_complete()`, `SQLGeneratorTool` unchanged — they use `create_llm_client()` / `claude_complete()`. | Medium |
| **Phase 1b: Vertex AI (later)** | Add `vertex_ai_client.py`; extend GCP's `get_llm_client()`: if `GCP_LLM_USE_VERTEX_AI=true` and creds set → return `GCPVertexAIClient()` before checking API key. **No changes** to agent, tools, or app.py. | Medium |

**Key insight:** Both paths use the same `LLMClient` interface and `google-genai` SDK. The only difference is client initialization (API key vs `vertexai=True` + project/location). Switching is an env var change.

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
| | - **Auth:** Prefer Workload Identity (Section 1.3); avoid mounting JSON keys in pods | |
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

## 2.2 GCP Kube vs Nonkube Architecture (Critical)

### 2.2.1 Kube: GKE ↔ EKS

| AWS (kube) | GCP (kube) |
|------------|-------------|
| **EKS** | **GKE** |
| EKS cluster + kubeconfig | GKE cluster + `gcloud container clusters get-credentials` |
| ALB/NLB for ingress | GKE Load Balancer (or Ingress) |
| CloudFront + S3 frontend | Load Balancer + Cloud CDN + GCS frontend (or Cloud Run for frontend) |
| K8s manifests (cloud_shared) | Same K8s manifests (Kubernetes is cloud-agnostic) |

**Kubernetes is cloud-agnostic** — the same `kubectl apply` manifests work on EKS and GKE. The main differences are: kubeconfig source (`eks_kubeconfig.py` vs `gke_kubeconfig.py`), Load Balancer URL resolution, and frontend (CloudFront vs Cloud CDN + GCS).

### 2.2.2 Nonkube: Cloud Run + Cloud CDN ↔ ECS + CloudFront

| AWS (nonkube) | GCP (nonkube) |
|---------------|---------------|
| **ECS** (API container + Spark tasks) | **Cloud Run** (API service) + **Cloud Run Jobs** (Spark) |
| **ALB** (load balancer) | **Cloud Run** (built-in HTTPS URL) or **Load Balancer** |
| **CloudFront** (CDN + HTTPS) | **Cloud CDN** (backend: Load Balancer or Cloud Run) |
| **S3** (frontend static) | **Cloud Storage** (frontend bucket) |
| **EventBridge** (Spark schedule) | **Cloud Scheduler** (Cloud Run Jobs trigger) |

**GCP nonkube architecture (cloud-native, no Kubernetes):**

1. **Cloud Run** (API service) — serverless containers, auto-scaling, HTTPS URL. Equivalent to ECS Fargate for the API.
2. **Cloud Run Jobs** (Spark) — one-off and scheduled jobs. Equivalent to ECS RunTask for Spark.
3. **Cloud Scheduler** — cron triggers for Cloud Run Jobs. Equivalent to EventBridge.
4. **Cloud Storage + Load Balancer + Cloud CDN** — frontend (static HTML/JS). Equivalent to S3 + CloudFront.
5. **Secret Manager** — secrets. Equivalent to Secrets Manager.

**Implementation order for nonkube:**
- Phase 1: Cloud Run API service (single URL, no frontend)
- Phase 2: Cloud Storage + Load Balancer + Cloud CDN for frontend
- Phase 3: Cloud Run Jobs + Cloud Scheduler for Spark

### 2.2.3 Implementation Priority

| Priority | Scope | Task | Rationale |
|----------|-------|------|-----------|
| **4.1** | kube | Deploy + verify | GKE + K8s is cloud-agnostic; follow AWS EKS flow |
| **4.2** | kube | Teardown + verify | Same as 4.1; kubectl/namespace checks are provider-agnostic |
| **4.3** | nonkube | Deploy + verify | Cloud Run + Cloud CDN; more GCP-specific |
| **4.4** | nonkube | Teardown + verify | Cloud Run service/job deletion |

**Rationale:** Kubernetes is standardized; GKE deploy/teardown mirrors EKS with minimal changes. Nonkube is more cloud-specific (ECS vs Cloud Run); do kube first for faster wins.

### 2.2.4 Kube Implementation Checklist (Priority 4.1, 4.2)

| Task | Reference | Status |
|------|-----------|--------|
| `tools/gcp/kube/gke_kubeconfig.py` | `tools/aws/kube/eks_kubeconfig.py` | ✓ Created |
| GCP kube stack: add remote state (shared_nondurable for delta bucket) | AWS kube main.tf | Pending |
| GCP deploy: apply (not just plan) for shared stacks | AWS deploy apply_stack | Pending |
| GCP deploy: apply kube stack when scope=kube/all | AWS run_deploy_kube | Pending |
| GCP deploy: kube_apply (K8s manifests) after GKE | AWS kube_apply | Pending |
| GCP teardown: destroy kube before shared | AWS teardown order | Pending |
| GCP teardown: kube_pre_destroy (delete CronJob, Job, namespace) | AWS kube_pre_destroy | Pending |

---

## 2.1 Comprehensive Provider-Specific Code Inventory

This section maps **all** places that need cloud-provider-specific code: `tools/`, `infra_terraform/live_deploy/`, `infra_terraform/modules/`, and `core_app/backend/env_utils/`. Use this to fill gaps and achieve GCP parity.

### 2.1.1 tools/

| Area | AWS exists | GCP exists | GCP gaps |
|------|------------|------------|----------|
| **Entry points** | `deploy.py`, `teardown.py` | — | Entire `tools/gcp/` tree |
| **kube/** | `deploy_kube.py`, `kube_apply.py`, `eks_kubeconfig.py`, `kube_pre_destroy.py` | — | `deploy_kube.py`, `kube_apply.py`, `gke_kubeconfig.py`, `kube_pre_destroy.py` |
| **nonkube/** | `deploy_nonkube.py`, `ecs_spark_schedule.py` | — | `deploy_nonkube.py` (Cloud Run Jobs + Cloud Scheduler) |
| **scope_shared/core/** | `backend.py` (S3/DynamoDB state), `terra_runner.py`, `terra_init.py`, `terra_var_handling.py` | — | `backend.py` (GCS state), `terra_runner.py`, etc. |
| **scope_shared/deploy/** | `build_and_push_images.py` (ECR), `setup_database.py` (Aurora), `ensure_secrets.py` (Secrets Manager), `bootstrap_state_backend.py` (S3) | — | Artifact Registry, Cloud SQL, Secret Manager, GCS state backend |
| **scope_shared/verify/** | `verify_all_deploy.py` | — | Same |
| **standalone/** | `doctor.py` | — | `doctor.py` (gcloud, GCP_PROJECT_ID, creds) |

**Suggested `tools/gcp/` layout:** See Phase 4.1 directory structure.

### 2.1.2 infra_terraform/live_deploy/

| Stack | AWS | GCP | GCP gaps |
|-------|-----|-----|----------|
| **kube/** | EKS, CloudFront, S3 frontend, Aurora ingress, S3 backend | GKE only, no backend block | GCS backend, frontend (Cloud CDN + GCS or Firebase), DB wiring |
| **nonkube/** | ECS, CloudFront, S3, S3 backend | README only | Full Terraform: Cloud Run Jobs, Cloud Scheduler, frontend |
| **scope_shared/durable/** | VPC, Aurora, S3 backend | VPC only, no backend | GCS backend, Cloud SQL |
| **scope_shared/durable_with_cooloff/** | Secrets Manager, S3 backend | — | Secret Manager, GCS backend |
| **scope_shared/nondurable/** | S3 buckets (delta, artifacts), ECR, S3 backend | GCS delta bucket only | GCS backend, Artifact Registry, artifacts bucket |

**Tasks:**
- Add `backend "gcs"` block to all GCP live_deploy stacks (bucket, prefix from vars).
- Add `live_deploy/gcp/scope_shared/durable_with_cooloff/` (Secret Manager).
- Extend `live_deploy/gcp/scope_shared/nondurable/` (Artifact Registry, artifacts bucket).
- Extend `live_deploy/gcp/scope_shared/durable/` (Cloud SQL).
- Add `live_deploy/gcp/nonkube/main.tf` (Cloud Run Jobs, Cloud Scheduler).
- Extend `live_deploy/gcp/kube/` (frontend, DB wiring).

### 2.1.3 infra_terraform/modules/

| Module | AWS | GCP | GCP gaps |
|--------|-----|-----|----------|
| **Compute** | `eks/`, `ecs/` | `gke/` | — (GKE exists) |
| **Networking** | `primitives/vpc/` | `primitives/vpc/` | — |
| **Storage** | `primitives/s3_bucket/` | `primitives/gcs_bucket/` | — |
| **Container registry** | `primitives/ecr/` | — | `primitives/artifact_registry/` |
| **Database** | `primitives/aurora/` | — | `primitives/cloud_sql/` |
| **Secrets** | (Secrets Manager in live_deploy) | — | `primitives/secret_manager/` |
| **Frontend/CDN** | `primitives/cloudfront/` | — | `primitives/cloud_cdn/` or Firebase Hosting |
| **Serverless jobs** | (ECS in ecs/) | — | `cloud_run_jobs/`, `cloud_scheduler/` |

**Tasks:**
- Create `modules/gcp/primitives/artifact_registry/`.
- Create `modules/gcp/primitives/cloud_sql/`.
- Create `modules/gcp/primitives/secret_manager/`.
- Create `modules/gcp/primitives/cloud_cdn/` (or Firebase Hosting).
- Create `modules/gcp/cloud_run_jobs/`, `modules/gcp/cloud_scheduler/`.
- Review `modules/cloud_shared/k8s/`: `api-service*.yaml` use AWS LB annotations; add GKE equivalents if needed.

### 2.1.4 core_app/backend/env_utils/

| Area | AWS | GCP | GCP gaps |
|------|-----|-----|----------|
| **LLM** | `bedrock_client.py`, `get_llm_client()` | `gemini_api_client.py`, `get_llm_client()` | — (done) |
| **Object storage** | `s3_helpers.py`, `storage_backend.py` | `gcs_helpers.py`, `storage_backend.py` | — (done) |
| **Database** | `rds_data_api.py` | — | Cloud SQL client (psycopg2; no Data API equivalent) |

**Tasks:**
- LLM: done.
- Storage: done (gcs_helpers, GCSStorageBackend).
- DB: Add `gcp/cloud_sql_client.py` or use psycopg2 directly when Cloud SQL is deployed (Phase 4).

### 2.1.5 Suggested implementation order

1. **env_utils** — LLM ✓, GCS storage ✓. DB client when Cloud SQL exists.
2. **modules** — Add GCP primitives (artifact_registry, cloud_sql, secret_manager) so live_deploy can reference them.
3. **live_deploy** — Add GCS backend, durable_with_cooloff, extend nondurable/durable/kube/nonkube.
4. **tools/gcp** — Deploy/teardown/verify scripts mirroring `tools/aws/`.
5. **orchestrator** — `handle_gcp()` routes to `tools/gcp/`.

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
| | - Use **`google-genai`** SDK with `vertexai=True` | |
| | - **Standard (ADC):** `genai.Client(vertexai=True, project=..., location=...)` — SDK uses `GOOGLE_APPLICATION_CREDENTIALS` or metadata | |
| | - **Org-restricted (API keys disabled):** Load creds with `google.oauth2.service_account.Credentials.from_service_account_file(key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])`; pass `credentials=creds` | |
| | - Env: `GCP_PROJECT_ID`, `GCP_REGION`, `GOOGLE_APPLICATION_CREDENTIALS` (or explicit `credentials=` when ADC restricted) | |
| | - Optional: `GCP_VERTEX_MODEL` (e.g. `gemini-2.5-flash`) | |
| | - Same `client.models.generate_content()` / `generate_content_stream()` as AI Studio | |
| 3.2.4 | Extend GCP's `get_llm_client()`: add Vertex AI branch | Low |
| | - If `GCP_LLM_USE_VERTEX_AI=true` and creds available → `GCPVertexAIClient()` | |
| | - Else if `GOOGLE_AI_API_KEY` or `GEMINI_API_KEY` set → `GCPGeminiAPIClient()` | |
| 3.2.5 | No new `requirements.txt` entry — `google-genai` already in Phase 1; add `google-auth` if using explicit credentials | Low |
| 3.2.6 | Update `tools/gcp/scope_shared/verify/verify_all_deploy.py` | Low |
| | - Use factory (already cloud-agnostic); no change if factory returns Vertex client | |

### 3.3 GCP `get_llm_client()` selection logic

```
GCP env_utils/gcp/get_llm_client():
  if GCP_LLM_USE_VERTEX_AI == "true" and GOOGLE_APPLICATION_CREDENTIALS set:
    → GCPVertexAIClient (Vertex AI)
  elif GOOGLE_AI_API_KEY or GEMINI_API_KEY set:
    → GCPGeminiAPIClient (Google AI Studio)
  else:
    → None
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

### 3.5 Coexistence and migration path

Both clients implement `LLMClient`; the factory chooses one at runtime. No code changes elsewhere — agent, tools, and verify scripts use `create_llm_client()` and remain unaware of which backend is used.

**Migration from Google AI Studio to Vertex AI:** Set `GCP_LLM_USE_VERTEX_AI=true` and ensure `GOOGLE_APPLICATION_CREDENTIALS` is set. After migration, delete unused API keys from [Google Cloud API Credentials](https://console.cloud.google.com/apis/credentials) per security best practice.

---

## War Story: Unified Google Gen AI SDK

**creation:** Feb 2026  
**keywords:** Google Gen AI, python-genai, AI Studio, Vertex AI, authentication, unified SDK  
**difficulty:** 6  
**significance:** 8  

### Context

Google unified the Python interface for Gemini in late 2024 with the `google-genai` library. Previously, developers used `google-generativeai` for AI Studio and `google-cloud-aiplatform` for Vertex AI — two different SDKs, two different APIs. The new SDK merges both backends into one: once the client is initialized, `generate_content()` and `generate_content_stream()` are identical regardless of backend.

### The Authentication Hurdle

**The critical gotcha:** AI Studio and Vertex AI use **different authentication mechanisms**, and the unified SDK does not hide this.

| Backend | Auth | Best for |
|---------|------|----------|
| **AI Studio** | Simple API key string from [aistudio.google.com](https://aistudio.google.com/app/apikey) | Prototyping, testing new models (Gemini 2.0, 3.0) |
| **Vertex AI** | Service account JSON key or Application Default Credentials | Enterprise, production, compliance (HIPAA, SOC2) |

**Enterprise restriction:** Many GCP organizations disable Standard API Keys via org policy. In that case, you cannot use AI Studio's API key path; you must use Vertex AI with a service account.

### Resolution

1. **AI Studio path:** `client = genai.Client(api_key='...')` or set `GEMINI_API_KEY` / `GOOGLE_API_KEY` (latter takes precedence).
2. **Vertex AI path (ADC):** `client = genai.Client(vertexai=True, project='...', location='...')` — SDK uses `GOOGLE_APPLICATION_CREDENTIALS` or GKE/VM metadata.
3. **Vertex AI path (org-restricted):** Load credentials explicitly with `google.oauth2.service_account.Credentials.from_service_account_file(path, scopes=['https://www.googleapis.com/auth/cloud-platform'])` and pass `credentials=creds`.

### Takeaway

> One SDK, two auth paths. Design your `client_factory` to branch on env vars (`GCP_LLM_USE_VERTEX_AI`, `GOOGLE_AI_API_KEY`) so switching is configuration-only. Never hardcode which backend to use.

---

## Pre-refactor checklist (complete before AI implements Option A)

Do these **before** starting the refactor:

| # | Task | Notes |
|---|------|-------|
| 1 | **Phase 0 done** | `.env` has GCP vars (e.g. `GCP_PROJECT_ID`, `GOOGLE_AI_API_KEY`); `get_cloud_provider()` exists in `env_utils/cloud_shared/provider.py` |
| 2 | **No uncommitted breaking changes** | Commit or stash WIP; refactor will touch imports and file moves |
| 3 | **Tests pass (if any)** | Run existing tests so we can verify no regressions |
| 4 | **GCP API key (optional)** | If testing GCP LLM: create key at [aistudio.google.com](https://aistudio.google.com/app/apikey), add `GOOGLE_AI_API_KEY` to `.env` |

**Import strategy:** All callers will import from `backend.env_utils.cloud_shared.client_factory` (no re-export in `backend.llm`).

**After checklist:** Proceed with Phase 1 (Option A: provider `get_llm_client()`, factory move to `env_utils/cloud_shared`).

---

## References (as of Feb 2026)

- [python-genai (official)](https://github.com/googleapis/python-genai) — unified SDK for Gemini Developer API and Vertex AI
- [python-genai docs](https://googleapis.github.io/python-genai/) — API reference
- [Migrate from Google AI Studio to Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/migrate/migrate-google-ai) — differences, migration steps
- [Vertex AI SDK migration guide](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations/genai-vertexai-sdk) — `google-genai` replaces deprecated Vertex AI SDK
- [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key) — Google AI Studio API key setup
- [Configure application default credentials](https://cloud.google.com/vertex-ai/generative-ai/docs/start/gcp-auth) — Vertex AI auth in GCP
