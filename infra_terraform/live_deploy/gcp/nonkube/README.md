# infra_terraform/live_deploy/gcp/nonkube

GCP **nonkube** stack: Cloud Run (API) + Cloud Run Jobs (Spark bootstrap + schedule) + Cloud Scheduler + load balancer / CDN + remote state.

Mirrors [AWS nonkube](../aws/nonkube/main.tf) (ECS Fargate + EventBridge) with GCP equivalents.

## Contents

- `main.tf` — wires Cloud Run services/jobs, scheduler, frontend bucket/CDN, remote state from `scope_shared/durable` + `nondurable`
- `variables.tf` — project, region, image tags, Delta path vars, embedding env

## Deploy

From repo root (preferred):

```bash
python orchestrator.py deploy --provider gcp --scope nonkube --env dev
```

Direct Terraform entry is handled by `tools/gcp/nonkube/deploy_nonkube.py` (build, secrets, `setup_database`, analytics bootstrap).

## Related

- [scope_shared/durable/README.md](../scope_shared/durable/README.md) — VPC + Cloud SQL
- [docs/GCP_AWS_REFERENCE.md](../../../docs/GCP_AWS_REFERENCE.md)
