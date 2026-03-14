# What to Do to Build for Another Cloud Provider

**Purpose:** A thorough, step-by-step guide for implementing support for a new cloud provider (e.g., Oracle, Azure) based on the GCP implementation experience. If you read this later, you should be able to deduce completely and thoroughly what to do to create the entire set of code at the right dirs for another cloud provider.

**Reference implementation:** GCP (from zero to working deploy/teardown/verify). This doc distills what we learned so you don't repeat the painful iteration.

---

## 1. Critical Mindset: "Just Copy AWS" is a Pipe Dream

### 1.1 The Expectation vs Reality

| Expectation | Reality |
|-------------|---------|
| "Mimic AWS code in corresponding dirs; it will work" | Every component has provider-specific differences. Copy-paste leads to subtle failures. |
| "Same structure, same flow" | Structure is similar, but **every** file needs provider-specific logic. |
| "A few days of work" | GCP took many iterations over a long period; many explicit instructions were needed. |

### 1.2 Why It Fails

- **State backend:** AWS uses S3 + DynamoDB; GCP uses GCS (built-in locking); Oracle/Azure have their own backends.
- **Container registry:** ECR vs Artifact Registry vs OCIR vs ACR—different URLs, auth, CLI.
- **Database:** Aurora vs Cloud SQL vs Oracle DB vs Azure Database—different connection patterns.
- **Serverless compute:** ECS Fargate (in VPC) vs Cloud Run (outside VPC, needs connector) vs OCI Container Instances vs Azure Container Apps.
- **Secrets:** Secrets Manager vs Secret Manager vs Vault vs Key Vault.
- **Networking:** VPC connector (GCP) vs Fargate in VPC (AWS) vs different models elsewhere.

### 1.3 The Right Approach

1. **Document first** — Create `{PROVIDER}_AWS_REFERENCE.md` mapping every AWS component to its equivalent (or "gap").
2. **Implement in phases** — env_utils → tools/core → tools/deploy → Terraform modules → live_deploy.
3. **Validate each phase** — Don't move on until the current phase works.
4. **Expect iteration** — Many "small" differences compound; fix them incrementally.

---

## 2. Prerequisites and Reference Documents

### 2.1 Read These First

| Document | Purpose |
|----------|---------|
| `docs/GCP_AWS_REFERENCE.md` | Template for provider mapping; use as structure for Oracle/Azure |
| `docs/REFACTOR_PLAN_GCP_READINESS.md` | Phase breakdown, env vars, LLM strategy |
| `docs/learned/cloud_shared/COMMON_CLOUD_COMPONENTS.md` | Cross-cloud component mapping (including how many container images per provider and why) |
| `docs/war_stories/WAR_STORIES_CLOUD_SHARED.md` | War Stories 30–37 (multi-cloud lessons) |
| `docs/war_stories/WAR_STORIES_GCP.md` | GCP-specific lessons |

### 2.2 Create Your Provider Reference

Before writing code, create `docs/{PROVIDER}_AWS_REFERENCE.md` with:

- **Section 1:** `core_app/backend/env_utils/` — LLM client, storage helpers, storage backend
- **Section 2:** `infra_terraform/modules/` — Compute, primitives (VPC, bucket, registry, DB, secrets, CDN)
- **Section 3:** `infra_terraform/live_deploy/` — durable, durable_with_cooloff, nondurable, kube, nonkube
- **Section 4:** `tools/` — deploy.py, teardown.py, provider_config_handler, scope_shared/core, scope_shared/deploy, scope_shared/verify, kube, nonkube
- **Section 4b:** `config/cloud/` — `{provider}_deploy_config.yaml` (region blocks)
- **Section 4c:** `tools/cloud_shared/` — ensure_secrets (add provider branch)
- **Section 5:** Gaps — What exists in AWS but not in the new provider (import_preexist, pre-destroy, etc.)

For each row: AWS path | New provider path | Notes (or "GCP: create equivalent").

**Optional:** Create `docs/{PROVIDER}_RESEARCH.md` with provider-specific findings (state backend, object storage URL, LLM SDK, credentials, etc.) before coding. See Section 8.

---

## 3. Implementation Phases (Recommended Order)

### Phase 0: Foundation

**Goal:** Provider detection and env vars so later phases can branch on cloud.

| Task | Description |
|------|-------------|
| 0.1 | Add `.env` vars for the new provider (project/tenancy ID, region, credentials path, etc.) |
| 0.2 | Extend `env_utils/cloud_shared/provider.py` — add detection for the new provider. Detection order: (1) `CLOUD_PROVIDER` explicit; (2) provider-specific env vars. **Oracle example:** `OCI_TENANCY_OCID` or `OCI_CONFIG_PROFILE` or `OCI_CLI_PROFILE` set → oracle. **Azure example:** `AZURE_SUBSCRIPTION_ID` or `ARM_CLIENT_ID` set → azure. |
| 0.3 | Ensure `get_cloud_provider()` returns the new provider string (e.g. `"oracle"`, `"azure"`) when configured |

**Provider detection env vars (examples):**

| Provider | Env vars that imply provider |
|----------|-----------------------------|
| AWS | `CLOUD_REGION` + (`AWS_ACCESS_KEY_ID` or `AWS_PROFILE` or `AWS_BEDROCK_*`) |
| GCP | `GCP_PROJECT_ID` or `GOOGLE_APPLICATION_CREDENTIALS` |
| Oracle | `OCI_TENANCY_OCID` or `OCI_CONFIG_PROFILE` or `OCI_CLI_PROFILE` or `~/.oci/config` |
| Azure | `AZURE_SUBSCRIPTION_ID` or `ARM_CLIENT_ID` or `AZURE_CLIENT_ID` |

**Deliverable:** Code can branch on `cloud_provider == "oracle"` (or "azure") without breaking AWS/GCP.

---

### Phase 1: core_app env_utils (LLM + Storage)

**Goal:** The app can run on the new provider for LLM and file operations.

#### 1.1 LLM Client

| Task | Description |
|------|-------------|
| 1.1.1 | Create `core_app/backend/env_utils/{provider}/__init__.py` |
| 1.1.2 | Create `core_app/backend/env_utils/{provider}/{llm}_client.py` implementing `LLMClient` |
| 1.1.3 | Add `get_llm_client() -> Optional[LLMClient]` to the provider's `__init__.py` |
| 1.1.4 | Extend `env_utils/cloud_shared/client_factory.py` — add the new provider to the factory logic |
| 1.1.5 | Add `requirements.txt` entries for the provider's SDK |

**Reference:** `env_utils/gcp/gemini_api_client.py`, `env_utils/aws/bedrock_client.py`.

**Key:** All clients implement the same `LLMClient` interface. The factory chooses based on `CLOUD_PROVIDER` and env vars.

#### 1.2 Storage (Object Storage)

| Task | Description |
|------|-------------|
| 1.2.1 | Create `core_app/backend/env_utils/{provider}/object_storage_helpers.py` — `exists()`, `listdir()`, `isdir()` for provider URLs |
| 1.2.2 | Create `core_app/backend/env_utils/{provider}/storage_backend.py` implementing `StorageBackend` |
| 1.2.3 | Extend `env_utils/cloud_shared/storage_factory.py` — `detect_storage_type()` for provider URL scheme (e.g. `oci://` for OCI Object Storage; Azure: `https://{account}.blob.core.windows.net/` or `abfss://`) |
| 1.2.4 | Extend `storage_factory.get_storage_backend()` — add branch for the new storage type, return the new backend |

**Reference:** `env_utils/gcp/gcs_helpers.py`, `env_utils/aws/s3_helpers.py`. Note: `filesystem.py` uses the factory; no direct changes needed if factory is updated.

#### 1.3 Analytics / Spark (Object Storage for Delta)

| Task | Description |
|------|-------------|
| 1.3.1 | Extend `core_app/analytics/jobs/run_analytics.py` — add `if cloud_provider == "{provider}":` branch for Spark config. AWS uses S3A + ContainerCredentialsProvider; GCP uses `fs.gs.impl` + Application Default Credentials. Oracle/Azure need equivalent Hadoop/Spark config for their object storage. |
| 1.3.2 | Ensure `DELTA_TABLE_PATH` (or equivalent) supports the provider's URL scheme in Spark |

**Reference:** `run_analytics.py` lines ~121–133 (GCP branch); AWS branch uses `s3a` + credentials provider.

**Deliverable:** App can use the new provider for LLM, object storage, and analytics (Delta Lake) when `CLOUD_PROVIDER={provider}`.

---

### Phase 2: core_app Runtime (Agent Decoupling)

**Goal:** Remove any provider-specific imports from the agent path.

| Task | Description |
|------|-------------|
| 2.1 | Ensure `QueryAgent` and `SQLGeneratorTool` use `llm_client=create_llm_client()` (not `get_bedrock_client()` or similar) |
| 2.2 | Ensure `app.py` uses `create_llm_client()` for the agent |
| 2.3 | Audit: no direct imports of `bedrock_client`, `gemini_api_client`, etc. in agent or app |

**Deliverable:** Agent is cloud-agnostic; works with any provider via factory.

---

### Phase 3: tools/ Structure

**Goal:** Create the full `tools/{provider}/` directory structure.

#### 3.1 Directory Layout (Mirror AWS)

```
tools/{provider}/
├── deploy.py
├── teardown.py
├── provider_config_handler.py   # Region-specific config (AZs, subnets, cluster settings)
├── kube/
│   ├── deploy_kube.py
│   ├── {provider}_kubeconfig.py    # e.g. oke_kubeconfig.py, aks_kubeconfig.py
│   ├── kube_apply.py
│   └── kube_pre_destroy.py
├── nonkube/
│   └── deploy_nonkube.py
├── scope_shared/
│   ├── core/
│   │   ├── backend.py             # State bucket, region, stack_id
│   │   ├── terra_runner.py
│   │   ├── terra_init.py
│   │   ├── phases.py
│   │   └── resource_names.py
│   ├── deploy/
│   │   ├── setup_state_backend.py
│   │   ├── build_and_push_images.py
│   │   ├── ensure_secrets.py
│   │   ├── setup_database.py
│   │   └── deploy_common.py
│   └── verify/
│       ├── verify_all_deploy.py
│       └── verify_all_teardown.py
└── standalone/
    └── doctor.py
```

#### 3.2 Implementation Order

1. **config/cloud/{provider}_deploy_config.yaml** — Create first. Deploy scripts and provider_config_handler depend on it. Copy structure from `aws_deploy_config.yaml` or `gcp_deploy_config.yaml`; adapt region names and keys (e.g. OCI: availability domains, VCN subnets).

2. **tools/{provider}/provider_config_handler.py** — Create. Expose functions like `get_azs()`, `get_subnet_cidrs()`, `get_{cluster}_location()` that deploy scripts need. Uses `load_deploy_config(provider, region)`.

3. **scope_shared/core/** — Everything else depends on this.
   - `backend.py`: `resolve_region()`, `resolve_state_bucket()`, `stack_id_from_dir()`
   - `terra_runner.py`: `get_terra_env()`, `terra()`, `terra_capture()`
   - `terra_init.py`: `init_stack()`, `backend_config()` — **provider-specific backend block**
   - `phases.py`: `deploy_phases()`, `teardown_phases()` (can reuse from cloud_shared if extracted)
   - `resource_names.py`: Cluster name, registry repo, log names

4. **scope_shared/deploy/setup_state_backend.py** — Create state bucket (or equivalent) if missing.

5. **scope_shared/deploy/build_and_push_images.py** — Push Docker images to provider's registry.

6. **deploy.py** — Wire phases: doctor → bootstrap → durable_with_cooloff → durable → nondurable → ensure_secrets → build → apply kube/nonkube.

7. **teardown.py** — Reverse order: kube/nonkube → nondurable → durable → durable_with_cooloff.

8. **scope_shared/verify/verify_all_deploy.py** — Health check, query test (use `create_llm_client()`).

9. **standalone/doctor.py** — Pre-flight checks: CLI, credentials, env vars, required APIs.

10. **kube/** and **nonkube/** — Deploy and teardown for each scope.

#### 3.3 Shared Components (Must Extend for New Provider)

These components live in `tools/cloud_shared/` or `config/` and **must be extended** when adding a provider. They are easy to miss.

| Component | Location | What to do |
|-----------|----------|------------|
| **ensure_secrets** | `tools/cloud_shared/ensure_secrets.py` | Add `elif provider == "{provider}":` branch. AWS uses Secrets Manager; GCP uses Secret Manager. Implement provider-specific logic to set OPENAI_API_KEY, PGPASSWORD, etc. in the provider's secret store. Update `--provider` choices in argparse. |
| **provider_config_handler** | `tools/{provider}/provider_config_handler.py` | Create this file. AWS has `get_azs()`, `get_subnet_cidrs()`; GCP has `get_gke_location()`, `get_initial_node_count()`. Oracle needs equivalent (e.g. availability domains, subnet CIDRs, OKE location). Uses `load_deploy_config(provider, region)` from `tools/cloud_shared/provider_config_utils.py`. |
| **Deploy config YAML** | `config/cloud/{provider}_deploy_config.yaml` | Create this file. Structure: `default:` block + region blocks (e.g. `us-ashburn-1`, `us-phoenix-1` for Oracle). Each region block: `network.azs`, `network.public_subnet_cidrs`, `network.private_subnet_cidrs`, `compute.desired_nodes`, etc. Reference: `config/cloud/aws_deploy_config.yaml`, `config/cloud/gcp_deploy_config.yaml`. |
| **provider_config_utils** | `tools/cloud_shared/provider_config_utils.py` | No code change—it loads `config/cloud/{provider}_deploy_config.yaml` by provider name. Just ensure the YAML file exists. |

**Deliverable:** Deploy scripts can load region-specific config; secrets can be ensured for the new provider.

---

### Phase 4: Terraform Modules

**Goal:** Reusable modules for the new provider's resources.

#### 4.1 Module Mapping (from COMMON_CLOUD_COMPONENTS.md)

| AWS Module | GCP Equivalent | Oracle | Azure |
|------------|----------------|--------|-------|
| `primitives/s3_bucket/` | `primitives/gcs_bucket/` | `primitives/object_storage_bucket/` | `primitives/storage_account/` |
| `primitives/ecr/` | `primitives/artifact_registry/` | `primitives/ocir/` | `primitives/acr/` |
| `primitives/aurora/` | `primitives/cloud_sql/` | `primitives/oci_mysql/` or Oracle DB | `primitives/azure_database/` |
| `primitives/vpc/` | `primitives/vpc/` | `primitives/vcn/` | `primitives/vnet/` |
| `primitives/cloudfront/` | `primitives/cloud_cdn/` | CDN / FastConnect | `primitives/cdn/` |
| `eks/` | `gke/` | `oke/` | `aks/` |
| `ecs/` | `cloud_run/` | `container_instances/` | `container_apps/` |

#### 4.2 Create Modules

For each primitive and compute module:

1. Create `infra_terraform/modules/{provider}/primitives/{resource}/` (or `modules/{provider}/{compute}/`)
2. Add `main.tf`, `variables.tf`, `outputs.tf`
3. Top-of-file comment: `# Reference: infra_terraform/modules/aws/<module>`
4. Mirror inputs/outputs where the provider allows

---

### Phase 5: live_deploy Stacks

**Goal:** Environment-specific composition using the new provider's modules.

#### 5.1 Stack Layout

```
infra_terraform/live_deploy/{provider}/
├── scope_shared/
│   ├── durable_with_cooloff/    # Secrets
│   ├── durable/                 # VPC, DB
│   └── nondurable/              # Buckets, registry
├── kube/                        # GKE/OKE/AKS + CDN + frontend
└── nonkube/                     # Cloud Run/Container Instances/Container Apps
```

#### 5.2 Backend Block

Each stack needs a `backend` block. **This is provider-specific.**

| Provider | Backend | Config |
|----------|---------|--------|
| AWS | `s3` | bucket, key, region, dynamodb_table |
| GCP | `gcs` | bucket, prefix |
| Oracle | `oci` | namespace, bucket_name, state_name; uses OCI Object Storage. See [Terraform OCI backend](https://registry.terraform.io/providers/oracle/oci/latest/docs). |
| Azure | `azurerm` | storage_account_name, container_name, key. See [Terraform Azure backend](https://developer.hashicorp.com/terraform/language/settings/backends/azurerm). |

**Critical:** `tools/{provider}/scope_shared/core/terra_init.py` (or equivalent) must generate the correct backend block. Do not copy AWS's `backend_config()` for a non-AWS provider. Research the provider's Terraform backend docs before implementing.

#### 5.3 Remote State

Stacks depend on each other via `terraform_remote_state` (or `data`). durable → nondurable → kube/nonkube. Ensure:

- durable outputs: VPC ID, subnet IDs, DB endpoint, VPC connector (if applicable)
- nondurable outputs: Delta bucket, registry URL, artifacts bucket
- kube/nonkube read from shared_durable and shared_nondurable

---

### Phase 6: Orchestrator Wiring

| Task | Description |
|------|-------------|
| 6.1 | Add `handle_{provider}()` in `orchestrator.py` (mirror `handle_aws` / `handle_gcp`) |
| 6.2 | Add `"{provider}"` to `--provider` choices in argparse (e.g. `choices=["aws", "gcp", "oracle"]`) |
| 6.3 | Add `elif args.provider == "{provider}": handle_{provider}(args)` in the main routing block |
| 6.4 | Route deploy → `python tools/{provider}/deploy.py` |
| 6.5 | Route teardown → `python tools/{provider}/teardown.py` |
| 6.6 | Route verify → `python tools/{provider}/scope_shared/verify/verify_all_deploy.py` |
| 6.7 | Pass `--env`, `--scope`, `--region` to scripts |

**Reference:** `orchestrator.py` — `handle_aws()`, `handle_gcp()`, and the `if args.provider == "aws":` / `elif args.provider == "gcp":` routing block.

---

## 4. Provider-Specific Gotchas (Checklist)

### 4.1 State Backend

- [ ] Does the provider use a separate lock table (like DynamoDB) or built-in locking (like GCS)?
- [ ] What is the bucket/container naming convention? (AWS: account_id; GCP: project_id; Oracle/Azure: ?)
- [ ] What is the state key/prefix format?

### 4.2 Container Registry

- [ ] URL format (ECR: `{account}.dkr.ecr.{region}.amazonaws.com`; Artifact Registry: `{region}-docker.pkg.dev/{project}/{repo}`)
- [ ] Auth: `docker login` with what? (AWS: `aws ecr get-login-password`; GCP: `gcloud auth configure-docker`)
- [ ] Terraform resource for creating the repository?

### 4.3 Database

- [ ] Managed DB service name and Terraform resource
- [ ] Connection: RDS Data API vs direct psycopg2 vs provider-specific client
- [ ] Private IP: Does the serverless compute need a VPC connector (like GCP) or is it already in VPC (like AWS)?

### 4.4 Serverless Compute (Nonkube)

- [ ] Equivalent to ECS Fargate / Cloud Run
- [ ] Networking: In VPC or outside? If outside, how does it reach the DB? (VPC connector, Private Link, etc.)
- [ ] Scheduler: EventBridge vs Cloud Scheduler vs OCI Events vs Azure Logic Apps

### 4.5 Kubernetes (Kube)

- [ ] Managed K8s service (EKS, GKE, OKE, AKS)
- [ ] Kubeconfig: `aws eks update-kubeconfig` vs `gcloud container clusters get-credentials` vs provider CLI
- [ ] Load balancer: Same K8s manifests or provider-specific annotations?

### 4.6 Secrets

- [ ] Secrets service and Terraform resource
- [ ] How are secrets injected into containers? (Env vars, volume mount, etc.)

### 4.7 Required APIs / Permissions

- [ ] Does the provider require enabling APIs per project (like GCP)?
- [ ] What IAM roles/permissions are needed for deploy?

---

## 5. Validation Checklist

After each phase, validate before moving on.

### Phase 0

- [ ] `get_cloud_provider()` returns the new provider when configured
- [ ] No regression for AWS/GCP

### Phase 1

- [ ] `create_llm_client()` returns the new provider's client when `CLOUD_PROVIDER={provider}`
- [ ] `filesystem.exists("{provider}://...")` works (or equivalent URL scheme)
- [ ] Health endpoint reports credentials for the new provider
- [ ] `run_analytics.py` has provider branch for Spark object-storage config (if using analytics)

### Phase 2

- [ ] Agent works with the new provider's LLM client
- [ ] No provider-specific imports in agent or app

### Phase 3

- [ ] `config/cloud/{provider}_deploy_config.yaml` exists with at least one region block
- [ ] `tools/{provider}/provider_config_handler.py` exists and loads config
- [ ] `tools/cloud_shared/ensure_secrets.py` has `{provider}` branch (or deploy uses provider-specific ensure_secrets)
- [ ] `doctor.py` passes
- [ ] `setup_state_backend` creates state bucket
- [ ] `deploy.py --scope kube --env dev` (or nonkube) runs without error (may fail at Terraform if Phase 4/5 not done)
- [ ] `teardown.py` runs in reverse order

### Phase 4 & 5

- [ ] `tofu plan` succeeds for each stack
- [ ] `tofu apply` creates resources
- [ ] `verify_all_deploy.py` passes (health, query)

### Phase 6

- [ ] Orchestrator routes to the new provider's scripts correctly

---

## 6. Summary: What We Organized and What We Needed

### 6.1 What We Organized

1. **env_utils** — Cloud-agnostic interfaces (`LLMClient`, `StorageBackend`) in `cloud_shared/`; provider implementations in `aws/`, `gcp/`, etc.
2. **client_factory** — Single `create_llm_client()` that branches on `CLOUD_PROVIDER` and env vars.
3. **tools/** — Mirror structure: deploy.py, teardown.py, scope_shared/core, scope_shared/deploy, scope_shared/verify, kube, nonkube.
4. **Terraform** — Modules in `modules/{provider}/`; live config in `live_deploy/{provider}/`; backend block generated by tools.
5. **Reference doc** — `GCP_AWS_REFERENCE.md` as the mapping template.

### 6.2 What We Needed (Explicit Instructions)

1. **Phase order** — doctor → bootstrap → durable_with_cooloff → durable → nondurable → secrets → build → apply.
2. **State backend** — GCS has no DynamoDB; use `backend "gcs"` with bucket and prefix only.
3. **VPC connector** — Cloud Run is outside VPC; durable must create connector; nonkube must pass it.
4. **Artifact Registry** — Different URL format and auth than ECR.
5. **Required APIs** — Enable Cloud Storage, Cloud SQL, GKE, Artifact Registry, etc. before deploy.
6. **State bucket naming** — Use `project_id` not `account_id`.
7. **env_utils first** — Do not start with tools; the app must be cloud-agnostic first.
8. **Reference pattern** — Every GCP file has `# Reference: <AWS path>`.

### 6.3 For Oracle or Azure

Use this document as the checklist. Create `{PROVIDER}_AWS_REFERENCE.md` first. Implement in phases. Validate each phase. Expect to iterate. The structure is proven; the provider-specific details are what you fill in.

---

## 7. Import Preexist and Teardown Gaps: When to Implement

AWS has scripts that GCP does not yet have: `import_preexist/` (reconcile orphaned resources), `teardown/cloudfront_pre_destroy.py`, `teardown/durable_post_destroy.py`. For a new provider:

| Gap | Purpose | Recommendation |
|-----|---------|----------------|
| **import_preexist** | Import pre-existing resources into Terraform state before apply/destroy | **Defer** for v1. Implement when you have orphaned resources to reconcile. |
| **Pre-destroy** (e.g. Cloud CDN invalidation, CronJob deletion) | Clean up resources that block Terraform destroy | **Implement** if the provider has equivalent (e.g. OCI CDN pre-destroy). Kube pre-destroy (delete CronJob, Job, namespace) is **required** for kube scope. **GCP durable pre-destroy:** Cloud SQL + service networking peering—use `gcloud compute networks peerings delete` (Compute API), not tofu; Service Networking API blocks 40+ min. See `durable_pre_destroy.py`, WAR_STORIES_GCP §8. |
| **Post-destroy orphans** | Clean up resources Terraform doesn't manage | **Defer** for v1. Add when you encounter orphan cleanup needs. |

**Kube pre-destroy is required:** Before destroying the kube stack, delete CronJobs, Jobs, and optionally the namespace so Terraform can cleanly destroy. Reference: `tools/aws/kube/kube_pre_destroy.py`, `tools/gcp/kube/` (create equivalent).

---

## 8. Provider-Specific Research (Oracle / Azure Quick Reference)

Before implementing, research and document these for your provider. Use the gotchas checklist (Section 4) and fill in below.

### 8.1 Oracle (OCI)

| Topic | Research question | Notes |
|-------|-------------------|-------|
| **State backend** | Terraform OCI backend: namespace, bucket_name, state_name. Locking? | OCI Object Storage; check provider docs for lock mechanism |
| **Object Storage URL** | URL scheme for Spark/filesystem? `oci://` or `https://objectstorage.{region}.oraclecloud.com/n/{namespace}/b/{bucket}/o/...`? | OCI uses namespace + bucket + object; URL format may differ from S3/GS |
| **OCI GenAI** | SDK? Auth? `oci-sdk` or separate GenAI package? | OCI GenAI service; auth via instance principal or config file |
| **Credentials** | `~/.oci/config`, `OCI_CONFIG_PROFILE`, `OCI_TENANCY_OCID`, `OCI_USER_OCID`, `OCI_FINGERPRINT`, `OCI_KEY_FILE` | OCI CLI config format |
| **Container Instances** | In VCN or outside? How does it reach MySQL/Oracle DB? | May need Service Gateway or private endpoint |
| **OCI Vault** | API for secrets; how to inject into containers? | Vault secrets; reference by OCID |
| **OCI Events** | How to trigger batch jobs (Spark)? Event rule → Function? | OCI Events service |
| **Regions** | `us-ashburn-1`, `us-phoenix-1`, etc. Default? | OCI region format |
| **OCIR** | URL format: `{region}.ocir.io/{tenancy-namespace}/{repo}/{image}:{tag}`? Auth: `oci artifacts container login`? | Container registry |

### 8.2 Azure

| Topic | Research question | Notes |
|-------|-------------------|-------|
| **State backend** | `azurerm` backend: storage_account_name, container_name, key | Standard Terraform backend |
| **Blob Storage URL** | `abfss://` (ADLS Gen2) or `wasbs://`? Spark config? | Azure Data Lake Storage Gen2 for Spark |
| **Azure OpenAI** | SDK, auth (Entra ID, API key?) | Azure OpenAI Service |
| **Credentials** | `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` or `az login` | Service principal or CLI auth |
| **Container Apps** | In VNet or outside? Private endpoint for DB? | Azure Container Apps networking |
| **Key Vault** | Secrets API; reference in Container Apps | Azure Key Vault |
| **Logic Apps / Timer** | Scheduler for batch jobs | Azure Logic Apps or Timer trigger |
| **ACR** | URL: `{registry}.azurecr.io/{repo}:{tag}`? Auth: `az acr login`? | Azure Container Registry |

**Action:** Create a `docs/{PROVIDER}_RESEARCH.md` (or section in `{PROVIDER}_AWS_REFERENCE.md`) with your findings before coding.

---

## 9. References

| Document | Purpose |
|----------|---------|
| `docs/GCP_AWS_REFERENCE.md` | GCP ↔ AWS mapping (template for new providers) |
| `docs/REFACTOR_PLAN_GCP_READINESS.md` | GCP phases, env vars, LLM strategy |
| `docs/learned/cloud_shared/GCP_API_CLOUD_SQL_WIRING.md` | Cloud Run → Cloud SQL (VPC connector) |
| `docs/learned/cloud_shared/COMMON_CLOUD_COMPONENTS.md` | Cross-cloud component table |
| `config/cloud/aws_deploy_config.yaml` | Region config template (AZs, subnets) |
| `config/cloud/gcp_deploy_config.yaml` | GCP region config |
| `docs/war_stories/WAR_STORIES_CLOUD_SHARED.md` | War Stories 30–37 (multi-cloud) |
| `docs/war_stories/WAR_STORIES_GCP.md` | GCP-specific war stories |
