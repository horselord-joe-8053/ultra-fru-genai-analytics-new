# Kubernetes Manifests (cloud_shared)

Jinja2 templates for API deployment, LoadBalancer Service, and Spark analytics (bootstrap + CronJob). Rendered by `tools/cloud_shared/k8s_j2_render.py`; used by AWS EKS and GCP GKE kube deploy flows.

## File Inventory

| Template | Kind | Rendered for | Purpose |
|----------|------|--------------|---------|
| `api-deployment.yaml.j2` | Deployment | AWS or GCP | API pods; platform-specific env (aws-credentials/Bedrock vs CLAUDE/GOOGLE) |
| `api-service.yaml.j2` | Service | AWS or GCP | LoadBalancer; AWS: NLB or Classic ELB (`use_elb`); GCP: no annotations |
| `bootstrap-job.yaml.j2` | Job | AWS or GCP | One-off Spark analytics bootstrap |
| `spark-cronjob.yaml.j2` | CronJob | AWS or GCP | Periodic Spark analytics (`*/5 * * * *`) |

**Rendering:** `tools/cloud_shared/k8s_j2_render.render(template_name, context)` — runs locally (or in CI); cloud receives only the final YAML via kubectl. Requires `jinja2` (in `requirements.txt`).

---

## Context Variables

All templates expect `cloud_provider` ("aws" or "gcp"). Platform-specific:

| Variable | AWS | GCP |
|----------|-----|-----|
| `CONTAINER_TYPE` | eks | gke |
| `api-service` | `use_elb` (bool) for NLB vs Classic ELB | — |
| Spark command | hadoop-aws package | GCS connector jar |
| Env | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BEDROCK_* | CLOUD_PROVIDER, GCP_LLM_PROVIDER, CLAUDE_MODEL, GOOGLE_MODEL |

---

## How They Are Used

### AWS (tools/aws/kube/kube_apply.py)

- **Phase bootstrap:** `render("bootstrap-job", {...})`, `render("api-deployment", {...})`, `render("api-service", {cloud_provider, use_elb})`
- **Phase schedule:** `render("spark-cronjob", {...})`

### GCP (tools/gcp/kube/kube_apply.py)

- **Phase bootstrap:** `render("bootstrap-job", {...})`, `render("api-deployment", {...})`, `render("api-service", {cloud_provider})`
- **Phase schedule:** `render("spark-cronjob", {...})`

---

## References

- `docs/learned/cloud_shared/KUBE_LB.md` — NLB vs Classic ELB, annotation details
- `docs/learned/cloud_shared/ANALYTICS_AND_DATA.md` — Spark analytics pipeline
- `core_app/analytics/jobs/run_analytics.py` — Job invoked by all Spark manifests
