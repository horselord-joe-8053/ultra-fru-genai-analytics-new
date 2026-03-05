# Completed: GCP Kube UI Refactor

**Date:** 2025-02  
**Purpose:** Enable GCP kube scope to have a functional UI (frontend + API) like AWS kube. Previously, GCP kube only applied GKE + Cloud CDN; it lacked API deployment, LB wiring, and frontend sync.

**Reference:** AWS kube flow in `tools/aws/kube/deploy_kube.py`, `tools/aws/kube/kube_apply.py`.

---

## 1. Problem Statement

- **GCP kube** had GKE cluster + Cloud CDN + GCS frontend bucket, but:
  - No `kube_apply` (API, CronJob, Job not deployed to GKE)
  - No GKE LoadBalancer hostname wired into Cloud CDN (API routes `/query`, `/analytics` etc. were not reachable)
  - No frontend deploy to GCS or CDN invalidation
- **Verify** could not test kube endpoints because there was no base URL (CDN IP existed but API origin was not configured)

---

## 2. Architecture Overview

```
User → Cloud CDN (global forwarding rule IP)
         ├── / → GCS bucket (frontend static)
         └── /query, /analytics, /health, /version → Internet NEG → GKE LoadBalancer (fru-api-svc) → fru-api pods
```

- **Nonkube:** Cloud Run API → Serverless NEG → Cloud CDN (existing)
- **Kube:** GKE API (LoadBalancer svc) → Internet NEG (FQDN) → Cloud CDN (new)

---

## 3. Changes by Component

### 3.1 Cloud CDN Module (`infra_terraform/modules/gcp/primitives/cloud_cdn/`)

**variables.tf**
- Added `api_origin_hostname` (string, default null) — GKE LoadBalancer hostname for kube scope. Mutually exclusive with `cloud_run_service_name`.

**main.tf**
- Added locals: `use_cloud_run_api`, `use_internet_api`, `use_api`, `api_backend_id`
- **Internet NEG** (when `api_origin_hostname` set):
  - `google_compute_global_network_endpoint_group` — type `INTERNET_FQDN_PORT`, default_port 80
  - `google_compute_global_network_endpoint` — fqdn = hostname, port 80
  - `google_compute_backend_service` — backend group = Internet NEG, timeout_sec 60
- **URL map** — path_matcher uses `api_backend_id` (Cloud Run backend or Internet backend depending on scope)
- Path rules: `/query`, `/query/*`, `/analytics`, `/analytics/*`, `/version`, `/health` → API backend

**outputs.tf**
- Already had `url_map_name` — used for CDN invalidation

### 3.2 GCP Kube Stack (`infra_terraform/live_deploy/gcp/kube/`)

**variables.tf**
- Added `ingress_hostname` (string, default null) — GKE LB hostname; set after kube_apply creates the LB. Two-phase deploy: first apply without, then kube_apply, poll hostname, second apply with.

**main.tf**
- Pass `api_origin_hostname = var.ingress_hostname` to frontend module
- Added output `url_map_name` for CDN invalidation

### 3.3 GCP-Specific K8s Manifests (`infra_terraform/modules/cloud_shared/k8s/`)

| File | Purpose |
|------|---------|
| `api-service-gke.yaml` | GKE LoadBalancer Service (no AWS annotations). Port 80 → 5001. |
| `bootstrap-job-gcp.yaml` | One-off Spark job. Uses `gs://`, GCS connector jar, `CLOUD_PROVIDER=gcp`. No AWS credentials. |
| `spark-cronjob-gcp.yaml` | Periodic Spark CronJob. Same as bootstrap but schedule `*/5 * * * *`. |
| `api-deployment-gcp.yaml` | API Deployment. `CLOUD_PROVIDER=gcp`, `CONTAINER_TYPE=gke`. Secrets: db-credentials, app-credentials (OPENAI_API_KEY, CLAUDE_API_KEY, GOOGLE_AI_API_KEY with optional: true). No aws-credentials. |

### 3.4 GCP kube_apply.py (`tools/gcp/kube/kube_apply.py`)

**New file.** Applies K8s manifests to GKE.

- **Phases:** `bootstrap` (namespace, secrets, Job, API deployment, api-service-gke) and `schedule` (CronJob)
- **Secrets:** Fetches from GCP Secret Manager via `gcloud secrets versions access latest`
  - `db-credentials`: PGPASSWORD from durable `db_password_plain_secret_id`
  - `app-credentials`: OPENAI_API_KEY, CLAUDE_API_KEY, GOOGLE_AI_API_KEY from durable outputs
- **Images:** From nondurable `artifact_registry_app_url`, `artifact_registry_spark_url` + `:latest`
- **Delta:** `gs://{bucket}/delta/fru_sales`; bootstrap uses `run_analytics.py`, cronjob uses `periodic.py`
- **Kubeconfig:** Uses `gke_kubeconfig.py` before kubectl
- **Idempotency:** Skips bootstrap Job if `fru-analytics-bootstrap-kube` already has `status.succeeded >= 1` (unless `--force`)

### 3.5 GCP deploy_frontend (`tools/gcp/scope_shared/deploy/deploy_frontend.py`)

**New file.** GCP equivalent of AWS `deploy_frontend_to_s3`.

- `deploy_frontend_to_gcs(bucket, env, scope, project_id)` — npm install, npm run build (VITE_PROVIDER=gcp, VITE_SCOPE), `gsutil -m rsync -r -d dist gs://{bucket}`
- `invalidate_cloud_cdn(url_map_name, project_id)` — `gcloud compute url-maps invalidate-cdn-cache {url_map} --path "/*" --project {project}`

### 3.6 GCP deploy_kube.py (`tools/gcp/kube/deploy_kube.py`)

**Extended** from GKE-only apply to full flow.

1. **First apply** — GKE + frontend (Cloud CDN + GCS). If LB hostname known from prior run, pass `ingress_hostname` and skip second apply.
2. **kube_apply** — bootstrap + schedule (API, Job, CronJob, LoadBalancer svc)
3. **Poll LB hostname** — `kubectl get svc fru-api-svc -o jsonpath={.status.loadBalancer.ingress[0].hostname}` (up to 18 attempts, 10s interval)
4. **Second apply** (if hostname newly obtained or changed) — re-apply kube stack with `-var=ingress_hostname={hostname}` to wire Cloud CDN API origin
5. **Deploy frontend** — `deploy_frontend_to_gcs` + `invalidate_cloud_cdn`

### 3.7 Verify (`tools/gcp/scope_shared/verify/verify_all_deploy.py`)

- **Kube base URL:** Use `cloudfront_domain_name` (CDN IP) as `http://{cdn_ip}`. Previously looked for `load_balancer_url` or `ingress_url` which did not exist.

### 3.8 GCP kube_pre_destroy (`tools/gcp/kube/kube_pre_destroy.py`)

**New file.** Pre-destroy cleanup before kube stack destroy.

- Scale `fru-api` deployment to 0
- Delete `fru-api-svc` (LoadBalancer)
- Delete CronJob `fru-analytics-periodic-kube`
- Delete Job `fru-analytics-bootstrap-kube`
- Delete namespace `fru-kube`
- Uses `gke_kubeconfig.py`; skips if cluster not found

### 3.9 GCP Teardown (`tools/gcp/teardown.py`)

- Before destroying kube stack: call `k8s_pre_destroy_cleanup(args.env, region, stats)`
- Before destroying durable stack: call `pre_destroy_durable` (targeted Cloud SQL destroy → poll until gone → `gcloud compute networks peerings delete` + `tofu state rm`). Uses Compute API to avoid Service Networking "Producer services still using" block (40+ min). See `durable_pre_destroy.py` and WAR_STORIES_GCP §8.

---

## 4. File Summary

| Path | Action |
|------|--------|
| `infra_terraform/modules/gcp/primitives/cloud_cdn/variables.tf` | Modified — added `api_origin_hostname` |
| `infra_terraform/modules/gcp/primitives/cloud_cdn/main.tf` | Modified — Internet NEG + backend, locals |
| `infra_terraform/live_deploy/gcp/kube/variables.tf` | Modified — added `ingress_hostname` |
| `infra_terraform/live_deploy/gcp/kube/main.tf` | Modified — pass `api_origin_hostname`, output `url_map_name` |
| `infra_terraform/modules/cloud_shared/k8s/api-service-gke.yaml` | New |
| `infra_terraform/modules/cloud_shared/k8s/bootstrap-job-gcp.yaml` | New |
| `infra_terraform/modules/cloud_shared/k8s/spark-cronjob-gcp.yaml` | New |
| `infra_terraform/modules/cloud_shared/k8s/api-deployment-gcp.yaml` | New |
| `tools/gcp/kube/kube_apply.py` | New |
| `tools/gcp/scope_shared/deploy/deploy_frontend.py` | New |
| `tools/gcp/kube/deploy_kube.py` | Modified — full flow (kube_apply, LB poll, second apply, frontend) |
| `tools/gcp/scope_shared/verify/verify_all_deploy.py` | Modified — kube base URL from CDN IP |
| `tools/gcp/kube/kube_pre_destroy.py` | New |
| `tools/gcp/teardown.py` | Modified — pre-destroy kube before destroy |

---

## 5. Deploy Flow (GCP kube)

```
orchestrator deploy --provider gcp --scope kube --env dev --apply
  → deploy.py
    → Phase 9/10: run_deploy_kube
      1. Tofu apply (GKE + frontend, optionally with ingress_hostname if LB known)
      2. kube_apply --phase bootstrap
      3. kube_apply --phase schedule
      4. Poll kubectl for fru-api-svc LB hostname
      5. If hostname new/changed: Tofu apply with -var=ingress_hostname={hostname}
      6. deploy_frontend_to_gcs + invalidate_cloud_cdn
```

---

## 6. Teardown Flow (GCP)

**Kube scope:**
```
orchestrator teardown --provider gcp --scope kube --env dev --non-interactive
  → teardown.py
    → For kube stack:
      1. k8s_pre_destroy_cleanup (scale, delete svc, cronjob, job, namespace)
      2. tofu destroy
```

**Scope=all with --incl-dura / --incl-dura-all:** Before durable destroy, `pre_destroy_durable` runs: targeted Cloud SQL destroy → poll until instance gone → `gcloud compute networks peerings delete` (Compute API) → `tofu state rm` connection → full durable destroy. Avoids Service Networking API block (WAR_STORIES_GCP §8).

---

## 7. Differences: GCP vs AWS Kube

| Aspect | AWS | GCP |
|--------|-----|-----|
| API origin for CDN | ALB/NLB hostname → CloudFront custom origin | GKE LB hostname → Internet NEG → Cloud CDN |
| Secrets | AWS Secrets Manager (ARN) | GCP Secret Manager (secret ID) |
| Delta storage | s3a:// | gs:// |
| Spark packages | hadoop-aws | GCS connector jar only |
| LB annotations | AWS Load Balancer Controller (NLB) or in-tree (ELB) | None (GKE default external LB) |
| Pre-destroy | kube_pre_destroy + EKS SG cleanup + k8s-elb SG post-destroy | kube_pre_destroy only |

---

## 8. Prerequisites for GCP Kube Deploy

- GKE cluster created (durable, nondurable, nonkube applied first when scope=all)
- Images built and pushed to Artifact Registry
- Secrets in GCP Secret Manager (db_password, openai_api_key, claude_api_key, google_ai_api_key)
- `kubectl` and `gcloud` configured; `gke_kubeconfig.py` succeeds
- GKE nodes able to reach Cloud SQL (same VPC or Private Service Access) and GCS (default SA or Workload Identity)

---

## 9. Verification

- `orchestrator verify --provider gcp --scope all` — kube scope uses CDN IP as base URL; hits `/health`, `/query`, `/analytics` via Cloud CDN → Internet NEG → GKE LB.
