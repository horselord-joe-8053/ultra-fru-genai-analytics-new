
# infra_terraform/live_deploy/gcp/scope_shared/durable

**Durable** GCP stack: VPC + **Cloud SQL PostgreSQL** + secret re-exports from `durable_with_cooloff`.

Aligned with AWS `scope_shared/durable` (VPC + Aurora). PostgreSQL is slow to create/destroy — kept in durable so nondurable stacks (GCS, Artifact Registry) can churn independently.

## Resources

- VPC (`modules/gcp/primitives/vpc`)
- Private service connection + Cloud SQL instance (`modules/gcp/primitives/cloud_sql`)
- Outputs: network IDs, Cloud SQL connection name, secret IDs for OpenAI/DB password/LLM keys

## Deploy

```bash
python orchestrator.py deploy --provider gcp --scope all --env dev
# durable phases run inside tools/gcp/deploy.py before kube/nonkube apply
```

**Teardown:** Cloud SQL delete is async (minutes). Pre-destroy hooks in `tools/gcp/` target SQL before VPC peering teardown.

Manual `tofu plan` from this directory requires GCS backend config from `.env` (same vars as deploy). Prefer `python orchestrator.py deploy --provider gcp` for init/apply.
