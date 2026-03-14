# GCP ↔ AWS Reference

**Purpose:** Every GCP component references its AWS counterpart. Use this document to ensure parity and guide implementation.

**Building for Oracle, Azure, or another provider?** Use this doc as a template for `{PROVIDER}_AWS_REFERENCE.md`. See [WHAT_TO_DO_TO_BUILD_FOR_ANOTHER_CLOUD_PROVIDER.md](WHAT_TO_DO_TO_BUILD_FOR_ANOTHER_CLOUD_PROVIDER.md) for the full implementation guide.

---

## 1. core_app/backend/env_utils/

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/__init__.py` | `aws/__init__.py` | `get_llm_client()`; GCP uses Gemini API, AWS uses Bedrock |
| `gcp/gemini_api_client.py` | `aws/bedrock_client.py` | LLM client; implements `LLMClient` interface |
| `gcp/gcs_helpers.py` | `aws/s3_helpers.py` | `gcs_exists`, `gcs_listdir`, `gcs_isdir` ↔ `s3_exists`, `s3_listdir`, `s3_isdir` |
| `gcp/storage_backend.py` | `aws/storage_backend.py` | `GCSStorageBackend` ↔ `S3StorageBackend`; implements `StorageBackend` |
| — | `aws/rds_data_api.py` | GCP: use Cloud SQL + psycopg2 (no RDS Data API equivalent) |

**Reference pattern:** Each GCP file should have a docstring: `(reference: core_app/backend/env_utils/aws/<file>)`

---

## 2. infra_terraform/modules/

### 2.1 Compute / orchestration

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/gke/` | `aws/eks/` | GKE cluster ↔ EKS cluster; node pool, kubeconfig |
| — | `aws/ecs/` | GCP nonkube: use `cloud_run/` (to create) ↔ ECS |

### 2.2 Primitives

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/primitives/gcs_bucket/` | `aws/primitives/s3_bucket/` | Bucket: versioning, lifecycle, labels/tags |
| `gcp/primitives/vpc/` | `aws/primitives/vpc/` | VPC, subnets; GCP uses `google_compute_network` |
| `gcp/primitives/secret_manager/` | (inline in durable_with_cooloff) | Secret Manager ↔ Secrets Manager |

### 2.3 Gaps (GCP modules to create, reference AWS)

| GCP to create | AWS reference | Purpose |
|---------------|---------------|---------|
| `gcp/cloud_run/` | `aws/ecs/` | API service + Spark jobs (nonkube) |
| `gcp/primitives/artifact_registry/` | `aws/primitives/ecr/` | Container registry |
| `gcp/primitives/cloud_cdn/` | `aws/primitives/cloudfront/` | CDN + frontend origin |
| `gcp/primitives/cloud_sql/` | `aws/primitives/aurora/` | Database |

**Reference pattern:** Each GCP module `main.tf` should have a top comment: `# Reference: infra_terraform/modules/aws/<module>`

---

## 3. infra_terraform/live_deploy/

### 3.1 scope_shared/durable_with_cooloff

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../durable_with_cooloff/main.tf` | `aws/.../durable_with_cooloff/main.tf` | Secret Manager secrets: openai_api_key, db_password, db_password_plain |

### 3.2 scope_shared/durable

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../durable/main.tf` | `aws/.../durable/main.tf` | VPC ↔ VPC; GCP: add Cloud SQL (↔ Aurora) when ready |

### 3.3 scope_shared/nondurable

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../nondurable/main.tf` | `aws/.../nondurable/main.tf` | Delta bucket, artifacts bucket, ECR ↔ Artifact Registry |

### 3.4 kube

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/kube/main.tf` | `aws/kube/main.tf` | **Reference:** `infra_terraform/live_deploy/aws/kube/main.tf` |
| | | AWS: EKS + remote state (shared_durable, shared_nondurable) + CloudFront + S3 frontend + subnet tags + Aurora ingress |
| | | GCP: GKE only (minimal). **Add:** remote state, frontend (Cloud CDN + GCS), Cloud SQL ingress |

### 3.5 nonkube

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/nonkube/` | `aws/nonkube/main.tf` | **Reference:** `infra_terraform/live_deploy/aws/nonkube/main.tf` |
| | | AWS: ECS module + CloudFront + remote state (shared_durable, shared_nondurable) |
| | | GCP: **Create** `nonkube/main.tf` with Cloud Run (↔ ECS) + Cloud CDN (↔ CloudFront) + remote state |

**Reference pattern:** Each GCP live_deploy stack should have a top comment in `main.tf`: `# Reference: infra_terraform/live_deploy/aws/<path>`

---

## 4. tools/

### 4.1 Entry points

| GCP | AWS | Notes |
|-----|-----|-------|
| `tools/gcp/deploy.py` | `tools/aws/deploy.py` | Deploy orchestrator; phases, doctor, bootstrap, apply |
| `tools/gcp/teardown.py` | `tools/aws/teardown.py` | Teardown order, pre-destroy, post-destroy |

### 4.2 scope_shared/core

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../core/backend.py` | `aws/.../core/backend.py` | State bucket, region, stack_id, gcs_delta_bucket |
| `gcp/.../core/terra_runner.py` | `aws/.../core/terra_runner.py` | get_terra_env, terra, terra_capture |
| `gcp/.../core/terra_init.py` | `aws/.../core/terra_init.py` | init_stack |
| `gcp/.../core/phases.py` | `aws/.../core/phases.py` | PhaseTracker, deploy_phases, teardown_phases |
| `gcp/.../core/resource_names.py` | `aws/.../core/resource_names.py` | gke_cluster, cloud_run_service, log names |
| — | `aws/.../core/terra_var_handling.py` | GCP: create equivalent for TF_VAR_ mapping |

### 4.3 scope_shared/deploy

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../deploy/setup_state_backend.py` | `aws/.../deploy/setup_state_backend.py` | GCS bucket ↔ S3 bucket for state |
| — | `aws/.../deploy/build_and_push_images.py` | GCP: Artifact Registry |
| — | `aws/.../deploy/setup_database.py` | GCP: Cloud SQL setup |
| — | `aws/.../deploy/ensure_secrets.py` | GCP: Secret Manager values |
| — | `aws/.../deploy/deploy_frontend.py` | GCP: GCS + Cloud CDN |
| — | `aws/.../deploy/deploy_common.py` | GCP: apply_stack, tofu_output_json, etc. |

### 4.4 scope_shared/verify

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../verify/verify_all_deploy.py` | `aws/.../verify/verify_all_deploy.py` | Endpoints, LLM, Cloud Logging ↔ CloudWatch |
| `gcp/.../verify/verify_all_teardown.py` | `aws/.../verify/verify_all_teardown.py` | Namespace, Cloud Run ↔ ECS |

### 4.5 kube/

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/kube/gke_kubeconfig.py` | `aws/kube/eks_kubeconfig.py` | gcloud get-credentials ↔ aws eks update-kubeconfig |
| — | `aws/kube/deploy_kube.py` | GCP: run_deploy_kube (GKE apply, kube_apply) |
| — | `aws/kube/kube_apply.py` | GCP: kube_apply (same K8s manifests) |
| — | `aws/kube/kube_pre_destroy.py` | GCP: kube_pre_destroy |
| — | `aws/kube/teardown_orphan_cleanup.py` | GCP: GKE orphan cleanup if needed |

### 4.6 nonkube/

| GCP | AWS | Notes |
|-----|-----|-------|
| — | `aws/nonkube/deploy_nonkube.py` | GCP: deploy_nonkube (Cloud Run) |
| — | `aws/nonkube/ecs_spark_schedule.py` | GCP: Cloud Scheduler + Cloud Run Jobs |

### 4.7 standalone/

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/standalone/doctor.py` | `aws/standalone/doctor.py` | gcloud, GCP_PROJECT_ID ↔ aws, AWS profile |

### 4.8 scope_shared/import_preexist (GCP gaps)

| GCP | AWS | Notes |
|-----|-----|-------|
| — | `aws/.../import_preexist/durable_cooloff.py` | GCP: import pre-existing Secret Manager |
| — | `aws/.../import_preexist/durable.py` | GCP: import VPC, Cloud SQL |
| — | `aws/.../import_preexist/nonkube.py` | GCP: import Cloud Run |
| — | `aws/.../import_preexist/kube.py` | GCP: import GKE |

### 4.9 scope_shared/teardown

| GCP | AWS | Notes |
|-----|-----|-------|
| `gcp/.../teardown/durable_pre_destroy.py` | — | GCP: Cloud SQL targeted destroy + gcloud compute peerings delete (Compute API) + state rm. Avoids Service Networking API "Producer services still using" block (40+ min). See WAR_STORIES_GCP §8. |
| — | `aws/.../teardown/cloudfront_pre_destroy.py` | GCP: Cloud CDN pre-destroy |
| — | `aws/.../teardown/durable_post_destroy.py` | GCP: durable post-destroy orphans |

---

## 5. Implementation checklist

When implementing any GCP component:

1. **Read** the AWS reference file(s) listed above.
2. **Add** a docstring or top-of-file comment: `# Reference: <path to AWS>`
3. **Mirror** structure, outputs, and behavior where cloud APIs allow.
4. **Document** intentional differences (e.g., GCS vs S3, Secret Manager vs Secrets Manager).
