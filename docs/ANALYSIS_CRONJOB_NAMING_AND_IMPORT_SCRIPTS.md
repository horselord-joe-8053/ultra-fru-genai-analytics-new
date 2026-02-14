# Analysis: CronJob/Job Naming & Terraform Import Scripts

## 1. CronJob/Job: Are Kube and Nonkube Sharing Them?

**No.** They are **not shared**:

| Target | Bootstrap mechanism | Scheduler | Where |
|--------|---------------------|-----------|-------|
| **Kube** | Kubernetes Job `fru-analytics-bootstrap` | CronJob `fru-analytics-periodic` | EKS cluster, namespace `fru` |
| **Nonkube** | ECS one-off RunTask | EventBridge → ECS RunTask | ECS cluster |

- **Kube** uses `kube_apply.py` to apply manifests from `infra-modules/shared/k8s/` (bootstrap-job.yaml, spark-cronjob.yaml). These run in EKS.
- **Nonkube** uses `run_ecs_bootstrap()` in deploy.py — an ECS RunTask. No K8s resources.

They are mutually exclusive deployment targets. The CronJob/Job are **kube-only**.

### Should We Add Scope (kube|nonkube) to Names?

**Current**: `fru-analytics-bootstrap`, `fru-analytics-periodic`, namespace `fru`

**Arguments for adding scope** (e.g. `fru-analytics-bootstrap-kube`, namespace `fru-kube`):
- Clearer when viewing resources in AWS/console
- Future-proofing if we ever run multiple kube clusters (e.g. dev-kube + prod-kube)
- Consistency with frontend naming (`fru-dev-frontend-nonkube`, `fru-dev-frontend-kube`)

**Arguments against**:
- Redundant today — they only exist in kube
- More changes (manifests, bootstrap_helpers, kube_apply)
- Namespace `fru` is short and familiar

**Recommendation**: Optional. Not required for correctness. Add scope if you want consistency with other resources (e.g. frontend suffix) or expect multiple clusters.

---

## 2. Terraform Import Scripts: Python, Matching Current Stack Division

### Current Stack Division

| Stack | State key | Key resources |
|-------|-----------|---------------|
| `live-deploy-aws/shared/durable` | `fru/{env}/aws-shared-durable.tfstate` | VPC, subnets |
| `live-deploy-aws/shared/nondurable` | `fru/{env}/aws-shared-nondurable.tfstate` | S3 (delta, artifacts), ECR (app, spark) |
| `live-deploy-aws/nonkube` | `fru/{env}/aws-nonkube.tfstate` | ECS, ALB, frontend (CloudFront, S3, OAC), EventBridge, IAM, CloudWatch |
| `live-deploy-aws/kube` | `fru/{env}/aws-kube.tfstate` | EKS, frontend (CloudFront, S3, OAC) |

### Proposed Python Structure

```
tools/aws/
├── import_existing.py          # CLI entry point
├── import/
│   ├── __init__.py
│   ├── lib.py                   # Shared: init stack, run import, skip logic
│   ├── shared_durable.py        # VPC (by VPC ID from name lookup)
│   ├── shared_nondurable.py     # S3 buckets, ECR repos
│   ├── nonkube.py               # ECS, ALB, frontend, etc.
│   └── kube.py                  # EKS, frontend
```

### CLI

```bash
python tools/aws/import_existing.py --scope [shared-durable|shared-nondurable|nonkube|kube|all] --env dev
```

### Per-Stack Import Map

Resources are imported by Terraform address and AWS resource ID. IDs are derived from naming conventions (`{prefix}-{env}-...`).

| Stack | Resource address | AWS ID (how to get) |
|-------|------------------|---------------------|
| **shared/durable** | `module.vpc.aws_vpc.main` | `aws ec2 describe-vpcs --filters "Name=tag:Name,Values={prefix}-{env}*"` → VpcId |
| **shared/nondurable** | `module.delta_bucket.aws_s3_bucket.bucket` | `{prefix}-{env}-delta` (bucket name) |
| | `module.artifacts_bucket.aws_s3_bucket.bucket` | `{prefix}-{env}-artifacts` |
| | `module.ecr_app.aws_ecr_repository.repo` | `{prefix}-{env}-api` or from ECR list |
| | `module.ecr_spark.aws_ecr_repository.repo` | `{prefix}-{env}-spark` |
| **nonkube** | `module.frontend.aws_cloudfront_origin_access_control.frontend` | Look up by name `{prefix}-{env}-frontend-nonkube-oac` |
| | `module.frontend.aws_s3_bucket.frontend` | `{prefix}-{env}-frontend-nonkube-{account_id}` |
| | `module.frontend.aws_cloudfront_distribution.frontend` | Look up by Comment `{prefix}-{env}-frontend-nonkube` |
| | (ECS, ALB, etc. — more complex; legacy had separate ecs.sh) |
| **kube** | `module.frontend.aws_cloudfront_origin_access_control.frontend` | `{prefix}-{env}-frontend-kube-oac` |
| | `module.frontend.aws_s3_bucket.frontend` | `{prefix}-{env}-frontend-kube-{account_id}` |
| | `module.frontend.aws_cloudfront_distribution.frontend` | Comment `{prefix}-{env}-frontend-kube` |
| | `module.eks.aws_eks_cluster.main` | `{eks_cluster_name}` from env |

### Shared Library Logic (lib.py)

- `init_stack(stack_dir, env)` — reuse existing init (backend_config, tofu init)
- `import_resource(stack_dir, env, address, resource_id)` — run `tofu import` with get_tofu_env(), capture output
- `skip_if_not_in_aws(err_output)` — treat "NoSuchEntity", "ResourceNotFoundException", "Cannot import non-existent" as skip (idempotent)
- `skip_if_already_managed(err_output)` — "already managed" → success
- `lookup_*` helpers — boto3/CLI to get IDs (OAC by name, distribution by comment, etc.)

### Differences from Legacy Shell

| Legacy (shell) | New (Python) |
|----------------|--------------|
| Per-layer scripts (import-existing-frontend-ecs.sh, etc.) | Single CLI with `--scope` |
| `terragrunt import` | `tofu import` via subprocess |
| `import_one_resource` + `import_batch` | `import_resource` + loop over stack-specific map |
| Lookup via `aws cloudfront list-*` in script | Python + boto3 or subprocess |
| State lock: force-unlock + retry | Same logic in Python |

### Blocker: Data Sources During Import

**Nonkube** has `data.aws_ecs_cluster.main` — fails when ECS is INACTIVE. Import triggers full config eval.

**Options**:
1. Make the data source resilient (e.g. `try()` or `count` when cluster absent) — recommended so import works post-teardown.
2. Document manual AWS CLI fallback for orphaned CloudFront (as we did) — no code change, but no automated import for nonkube when ECS is gone.

---

## 3. Refactor Plan (No Code Yet)

### Phase 1: CronJob/Job Naming (Optional) — DONE

- [x] Add `-kube` suffix to Job/CronJob names and namespace `fru-kube`
- [x] Update: `infra-modules/shared/k8s/bootstrap-job.yaml`, `spark-cronjob.yaml`
- [x] Update: `bootstrap_helpers.py` (JOB_BOOTSTRAP, CRONJOB_PERIODIC, K8S_NAMESPACE)
- [x] Update: `kube_apply.py` references

### Phase 2: Import Scripts (Python)

- [ ] Create `tools/aws/import_existing.py` (CLI)
- [ ] Create `tools/aws/import/lib.py` (init, import_resource, skip logic)
- [ ] Create `tools/aws/import/shared_durable.py` — VPC
- [ ] Create `tools/aws/import/shared_nondurable.py` — S3, ECR
- [ ] Create `tools/aws/import/nonkube.py` — frontend (OAC, S3, distribution), optionally ECS/ALB
- [ ] Create `tools/aws/import/kube.py` — frontend, EKS
- [ ] Add `--import` or `import --scope X` to orchestrator (optional)

### Phase 3: Resilient Data Sources (Enables Import)

- [ ] Make `data.aws_ecs_cluster.main` in nonkube optional when cluster is INACTIVE
- [ ] Similar for any other data sources that fail during partial teardown
