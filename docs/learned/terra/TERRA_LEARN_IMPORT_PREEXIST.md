# Import pre-existing resources (post–brutal-removal state reconciliation)

## Why we need these scripts

### What happens when state and reality are out of sync

When AWS resources exist but are **not** in Terraform state (e.g. after brutal removal, partial teardown, or state loss), Terraform tries to **create** them on apply. AWS responds that they already exist, and apply fails.

**Brutal-removal** (legacy: `orchestration/aws/cli/resource-removal/remove-all-aws-resources.sh`) deletes via AWS API directly, so Terraform state is never updated. It **does not** delete (by design or AWS behavior):

- **IAM roles** (global; often left behind)
- **Secrets Manager** secrets (preserved on purpose)
- **KMS** keys and aliases (sometimes left behind)
- **CloudWatch** log groups
- **CloudFront Origin Access Control (OAC)** (distributions may be deleted; OAC can remain). OAC is now **region-scoped** (`{prefix}-{env}-frontend-{suffix}-{region}-oac`) so each region has its own OAC; avoids `OriginAccessControlInUse` on teardown when another region's distribution still references it.

### Exceptions you see

Typical errors when state and reality are out of sync:

| Exception / message | Meaning |
|---------------------|--------|
| `EntityAlreadyExists: Role with name ... already exists` | IAM role exists in AWS but not in Terraform state (e.g. EKS cluster role, node group role). |
| `AlreadyExistsException: An alias with the name ... already exists` | KMS alias exists in AWS but not in state. |
| `ResourceAlreadyExistsException: The specified log group already exists` | CloudWatch log group exists but not in state. |
| `OriginAccessControlAlreadyExists: An origin access control with the same name already exists` | CloudFront OAC exists but not in state (common after brutal removal). |
| `ResourceExistsException` (Secrets Manager) | Secret exists in AWS but not in state. |

To fix this, we **import** those existing resources into Terraform state so Terraform treats them as managed instead of trying to create them again. The scripts in this directory do that import per layer. They are safe to run even when nothing is left behind (resources that don't exist are skipped).

**Preferred approach:** Use Terraform-based teardown (`teardown.sh` / `teardown-resources-all.sh`) instead of brutal removal when possible, so state and AWS stay in sync and you rarely need these imports.

---

## What counts as one "layer"

**One layer = one Terragrunt apply/destroy unit:** a directory that has a `terragrunt.hcl` and that we run `terragrunt apply` or `terragrunt destroy` on during deploy/teardown.

- **We do NOT count** each `main.tf` under `module_infra_basic/aws/terra/modules/`. Those are **modules** (reusable Terraform code). One layer can use several modules (e.g. infrastructure uses vpc, aurora, iam, secrets-manager, s3-data).
- **We DO count** each distinct **layer name** under `*/terra/environments/{dev,prod}/` — i.e. each directory with a `terragrunt.hcl` that we apply/destroy as a single step.

So: **layer** = one entry in the deploy/teardown flow (e.g. "infrastructure", "ecs", "eks", "frontend-ecs", "frontend-eks"). Dev and prod share the same layer names; we have one import script per layer name, parameterized by environment.

## How many such layers exist

There are **5** Terragrunt layers that create AWS resources and can be affected by the brutal removal script:

| # | Layer name      | Terragrunt path (per env)                                      | Typical leftovers after brutal removal |
|---|-----------------|----------------------------------------------------------------|----------------------------------------|
| 1 | infrastructure  | `module_infra_basic/aws/terra/environments/{dev,prod}/infrastructure` | IAM roles, RDS subnet group, Secrets Manager (script preserves), KMS |
| 2 | ecs             | `module_infra_kubetypes/nonkube/aws/terra/environments/{dev,prod}/ecs` | CloudWatch log group, ALB, target group |
| 3 | eks             | `module_infra_kubetypes/kube/aws/terra/environments/{dev,prod}/eks`   | IAM roles, KMS alias/key, CloudWatch log group |
| 4 | frontend-ecs    | `module_infra_basic/aws/terra/environments/{dev,prod}/frontend-ecs`   | CloudFront OAC, S3 bucket, CloudFront distribution |
| 5 | frontend-eks    | `module_infra_basic/aws/terra/environments/{dev,prod}/frontend-eks`   | CloudFront OAC, S3 bucket, CloudFront distribution |

## Import script coverage

All import scripts live in **`orchestration/terraform/import_preexist/`**. They share a common library:

- **`common/lib_import_common.sh`** — Bootstrap (REPO_ROOT, logger, env), argument parsing, env validation, directory check + `cd`, `terragrunt init` (strict/soft), state-lock parsing and force-unlock retry, `import_one_resource`, and `import_batch`. Scripts source this and call the helpers; no change to CLI or callers.

| Layer          | Script | Used in deploy? |
|----------------|--------|------------------|
| infrastructure | `import-existing-infrastructure.sh` | Yes (before infrastructure plan/apply) |
| ecs            | `import-existing-ecs.sh` | Yes (before ECS plan/apply) |
| eks            | `import-existing-eks.sh` | Yes (before EKS plan/apply) |
| frontend-ecs   | `import-existing-frontend-ecs.sh` | Yes (before frontend-ecs plan/apply) |
| frontend-eks   | `import-existing-frontend-eks.sh` | Yes (before frontend-eks plan/apply) |

All five layers have a dedicated import script. `orchestration/terraform/deploy.sh` runs each layer’s import script just before that layer’s plan/apply (per-layer, so only the layers you’re deploying get their import run).

**Import before destroy (teardown):** `teardown-resources-all.sh` runs the relevant import script(s) *before* each layer's `terragrunt destroy` (infrastructure before shared destroy; EKS + frontend-eks before EKS destroy; ECS + frontend-ecs before ECS destroy). If state was empty but AWS still has resources, destroy can then remove them. All import scripts accept `dev`, `staging`, or `prod`.

### Teardown-mode reconciliation details (recent learnings)

- **Purpose before destroy:** imports in teardown are **only for reconciliation**. They make sure Terraform state sees any leftover AWS resources so `terragrunt destroy` can actually delete them instead of no-op’ing. If a resource does not exist or is already in state, that is **not** a fatal error.
- **Benign errors we now classify as non-fatal:**
  - `Resource already managed by Terraform` → treated as **OK (already in state)**.
  - `Cannot import non-existent remote object` and similar (`NoSuchEntity`, `ResourceNotFoundException`, `does not exist`, `NoSuchKey`, etc.) → treated as **Skip (resource does not exist in AWS)**.
  - Terragrunt dependency warnings like *“... is a dependency of ./terragrunt.hcl but detected no outputs, but mock outputs provided ...”* are expected when using `mock_outputs` for unapplied dependencies; imports for teardown don’t require those outputs.
- **State lock handling during import:** when Terraform prints `Error acquiring the state lock`, the shared helper:
  - Parses the lock ID from the log.
  - Runs `terragrunt force-unlock -force <LOCK_ID>`.
  - Retries the import once and then re-classifies the result (success, already-managed, non-existent, or real failure).
  This prevents stale locks from breaking reconcile imports during teardown.

## Quick reference

- **Run all imports for one env (manual):**
  - `./orchestration/terraform/import_preexist/import-existing-infrastructure.sh dev fru`
  - `./orchestration/terraform/import_preexist/import-existing-ecs.sh dev fru`
  - `./orchestration/terraform/import_preexist/import-existing-eks.sh dev fru`
  - `./orchestration/terraform/import_preexist/import-existing-frontend-ecs.sh dev fru`
  - `./orchestration/terraform/import_preexist/import-existing-frontend-eks.sh dev fru`
- **Deploy** (runs EKS + frontend-eks imports automatically for EKS path; ECS + frontend-ecs for ECS path):  
  `./orchestration/terraform/deploy.sh dev eks` or `dev ecs` or `dev all`.

Run scripts from repo root or with correct `REPO_ROOT`.

## New project (fru-genai-analytics-new)

Import is implemented in Python under `tools/aws/scope_shared/import_preexist/`:

- **`_common.py`** — Shared logic: `import_one_resource`, `import_batch`, skip patterns
- **`nonkube.py`** — Nonkube: IAM roles, S3 frontend bucket, CloudFront OAC, ECS-layer (CloudWatch log groups, ALB, target group, security groups, security group rules: tasks_from_alb, aurora_from_ecs)
- **`kube.py`** — Kube: EKS IAM roles, S3 frontend bucket, CloudFront OAC
- **`run_import.py`** — Standalone entry point

**Deploy:** Runs import before each stack's apply (nonkube: `deploy_nonkube.py`, kube: `deploy_kube.py`).

**Teardown:** Runs import before each stack's destroy (nonkube, kube) so orphaned resources are adopted into state and destroy can remove them. See `tools/aws/teardown.py`.

**Standalone:**
```bash
PYTHONPATH=. python tools/aws/scope_shared/import_preexist/run_import.py --scope nonkube --env dev
PYTHONPATH=. python tools/aws/scope_shared/import_preexist/run_import.py --scope all --env dev --region us-east-1
```

## Ideal vs. current approach (solution selection)

### The "ideal" approach (import only IAM roles)

A more principled strategy is to **import only IAM roles** (which are global and often left behind by brutal removal) and treat other "already exists" errors as **surprises**. When apply fails with `ResourceAlreadyExistsException` for something other than IAM:

1. **Destroy** the orphaned resource in AWS (or via Terraform if state is partially correct).
2. **Recreate** it via Terraform apply.

This keeps imports minimal and makes unexpected leftovers visible instead of silently adopting them.

### Why we use broader pre-deploy import (current choice)

For **convenience and simplicity**, we use a **broader pre-deploy import** that brings into state all resources that commonly cause `ResourceAlreadyExistsException` after brutal removal or partial teardown:

- IAM roles
- CloudWatch log groups
- ALB, target group, security groups
- S3 bucket, CloudFront OAC

**Benefits:** One deploy command works without manual intervention; no need to destroy/recreate when state and reality drift.

**Risks:** We may adopt resources that were created outside Terraform or by a different config. If config has changed, imported resources might not match desired state; plan will show drift. For production, prefer Terraform-based teardown so state stays in sync and these imports are rarely needed.

See `tools/aws/scope_shared/import_preexist/` for the implementation.

## See also

- **Deployment errors** — Phase 2 Terraform "subnet group / VPC mismatch", S3 bucket empty, frontend invalid bucket, Docker not running, Terraform plugin checksum: see War Stories 12, 16, 17, 23.

