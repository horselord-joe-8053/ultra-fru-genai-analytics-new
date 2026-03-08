# Kubernetes Manifests (cloud_shared)

Kubernetes manifests for API deployment, LoadBalancer Service, and Spark analytics (bootstrap + CronJob). Used by AWS EKS and GCP GKE kube deploy flows.

## File Inventory

| File | Kind | Scope | Purpose |
|------|------|-------|---------|
| `api-deployment.yaml` | Deployment | AWS | API pods on EKS; aws-credentials, Bedrock |
| `api-deployment-gcp.yaml` | Deployment | GCP | API pods on GKE; CLAUDE/GOOGLE keys, no AWS creds |
| `api-service.yaml` | Service | AWS | LoadBalancer → NLB (default) |
| `api-service-elb.yaml` | Service | AWS | LoadBalancer → Classic ELB (`--elb` flag) |
| `api-service-gke.yaml` | Service | GCP | LoadBalancer for GKE (no AWS annotations) |
| `bootstrap-job.yaml` | Job | AWS | One-off Spark analytics bootstrap |
| `bootstrap-job-gcp.yaml` | Job | GCP | One-off Spark analytics bootstrap |
| `spark-cronjob.yaml` | CronJob | AWS | Periodic Spark analytics (`*/5 * * * *`) |
| `spark-cronjob-gcp.yaml` | CronJob | GCP | Periodic Spark analytics (`*/5 * * * *`) |

---

## API Service Manifests

Three variants for the same Service (`fru-api-svc`): selector, ports, and type are identical. Only annotations differ.

### api-service.yaml vs api-service-elb.yaml (AWS)

| | api-service.yaml | api-service-elb.yaml |
|---|-----------------|---------------------|
| **When used** | Default (no `--elb`) | `kube_apply --elb` |
| **Load balancer** | NLB (AWS Load Balancer Controller) | Classic ELB (in-tree cloud provider) |
| **Annotations** | `aws-load-balancer-scheme`, `aws-load-balancer-type: external`, `aws-load-balancer-nlb-target-type: instance` | `aws-load-balancer-scheme` only |
| **Requires** | AWS Load Balancer Controller installed | None (in-tree built into EKS) |

**Selection:** `tools/aws/kube/kube_apply.py` chooses `api-service-elb.yaml` if `args.elb` else `api-service.yaml`. The `--elb` flag is passed from `tools/aws/deploy.py` when deploying kube.

### api-service-gke.yaml (GCP)

- No AWS-specific annotations; GKE creates external LoadBalancer by default.
- Uses: `tools/gcp/kube/kube_apply.py` applies it in bootstrap phase (always, no flag).

---

## API Deployment Manifests

| | api-deployment.yaml | api-deployment-gcp.yaml |
|---|---------------------|-------------------------|
| **Scope** | AWS EKS | GCP GKE |
| **CONTAINER_TYPE** | `eks` | `gke` |
| **Credentials** | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (secretKeyRef); AWS_BEDROCK_* | CLAUDE_API_KEY, GOOGLE_AI_API_KEY (optional) |
| **LLM** | Bedrock via env vars | GCP_LLM_PROVIDER, CLAUDE_MODEL, GOOGLE_MODEL |
| **Shared** | PG*, LOG_LEVEL, ALLOWED_ORIGINS, probes, ports, etc. (~85%) |

Both use `${VAR}` substitution; `kube_apply` passes `api_subs` with platform-specific values.

---

## Spark Job Manifests

### Bootstrap vs CronJob

- **Bootstrap (Job):** One-off run at deploy. Populates `batch_analytics` for UI dashboards.
- **CronJob:** Scheduled every 5 minutes (`*/5 * * * *`). Recurring analytics.

### AWS vs GCP

| | bootstrap-job / spark-cronjob | bootstrap-job-gcp / spark-cronjob-gcp |
|---|------------------------------|--------------------------------------|
| **Packages** | `io.delta:delta-spark_2.12:3.1.0,org.apache.hadoop:hadoop-aws:3.3.4` | `io.delta:delta-spark_2.12:3.1.0` |
| **Jars** | — | `gcs-connector-hadoop3-2.2.7-shaded.jar` |
| **Storage** | S3 (s3a://) | GCS (gs://) |
| **Credentials** | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (Bootstrap: value; CronJob: secretKeyRef) | CLOUD_PROVIDER=gcp; ADC for GCS |
| **Shared** | PG*, DELTA_ROOT, DELTA_TABLE_PATH, run_analytics.py entry (~80%) |

---

## How They Are Used

### AWS (tools/aws/kube/kube_apply.py)

- **Phase bootstrap:** `api-deployment.yaml`, then `api-service.yaml` or `api-service-elb.yaml` (based on `--elb`), `bootstrap-job.yaml`
- **Phase schedule:** `spark-cronjob.yaml`
- **Substitution:** `render()` replaces `${VAR}` with values from `api_subs` / `subs`

### GCP (tools/gcp/kube/kube_apply.py)

- **Phase bootstrap:** `bootstrap-job-gcp.yaml`, `api-deployment-gcp.yaml`, `api-service-gke.yaml`
- **Phase schedule:** `spark-cronjob-gcp.yaml`
- **Substitution:** `_render()` for Job/Deployment/CronJob; `api-service-gke.yaml` has no placeholders (applied as-is)

---

## DRY Considerations

- **api-deployment:** ~85% overlap with api-deployment-gcp; could merge via Jinja2 with `cloud_provider` conditionals.
- **bootstrap-job:** ~80% overlap with bootstrap-job-gcp; same for spark-cronjob pair.
- **api-service:** api-service-elb differs only by 2 annotation lines; api-service-gke differs by no annotations. Could merge into one template with optional annotation block.
- **Recommendation:** Jinja2 templates (`.yaml.j2`) with `cloud_provider` and `use_nlb`/`use_elb` variables; single template per resource type. See prior discussion for effort vs benefit.

---

## References

- `docs/learned/cloud_shared/KUBE_LB.md` — NLB vs Classic ELB, annotation details
- `docs/learned/cloud_shared/ANALYTICS_AND_DATA.md` — Spark analytics pipeline
- `core_app/analytics/jobs/run_analytics.py` — Job invoked by all Spark manifests
