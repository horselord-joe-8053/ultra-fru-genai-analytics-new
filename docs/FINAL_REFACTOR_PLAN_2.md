# FRU GenAI Analytics: Final Refactor Plan 2 — Multi-Region Support

**Status**: Plan (implementation pending)  
**Created**: 2026-02-10  
**Prerequisite**: [FINAL_REFACTOR_PLAN.md](./FINAL_REFACTOR_PLAN.md) implemented (Phase 5 complete)

**Purpose**: Add `--region` support to deploy/teardown, enable multi-region state isolation, and provide a one-time migration for existing state.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Target Usage](#2-target-usage)
3. [Design: Region in State Key](#3-design-region-in-state-key)
4. [Implementation Tasks](#4-implementation-tasks)
5. [Migration Flow](#5-migration-flow)
6. [Multi-Region Config](#6-multi-region-config)
7. [References](#7-references)

---

## 1. Executive Summary

After FINAL_REFACTOR_PLAN.md is complete, this plan adds:

- **`--region`** flag to `deploy.py`, `teardown.py`, and related tools
- **`CLOUD_REGION`** fallback when `--region` is omitted
- **Region in state key** so each region has isolated Terraform state
- **`migrate_state_to_region_key.py`** for one-time migration of existing state from old keys to region-scoped keys

---

## 2. Target Usage

After implementation, these commands will work:

```bash
# Migration (one-time, for existing deployments)
python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --dry-run
python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --execute

# Deploy / teardown
python tools/aws/deploy.py --scope nonkube --env dev --region us-east-1
python tools/aws/deploy.py --scope nonkube --env dev  # uses CLOUD_REGION
python tools/aws/teardown.py --scope all --env dev --region us-east-1 --force
```

**Region resolution order**:

1. `--region` (CLI)
2. `CLOUD_REGION` (env)
3. `us-east-1` (hard default)

---

## 3. Design: Region in State Key

### Current (pre–Plan 2)

```
key = {prefix}/{env}/{stack_id}.tfstate
```

Example: `fru/dev/aws-shared-durable.tfstate`

### After Plan 2

```
key = {prefix}/{env}/{region}/{stack_id}.tfstate
```

Example: `fru/dev/us-east-1/aws-shared-durable.tfstate`

**Backend config** (`tools/aws/_backend.py`):

- Add optional `region` parameter to `backend_config(stack_dir, env, region=None)`
- When `region` is provided, use key `{prefix}/{env}/{region}/{stack_id}.tfstate`
- When `region` is `None` (legacy mode), use key `{prefix}/{env}/{stack_id}.tfstate` for backward compat during migration

**Recommendation**: Always require `region` after migration; remove legacy key format once all state is migrated.

---

## 4. Implementation Tasks

| # | Task | Path / Scope |
|---|------|--------------|
| 1 | Add `region` param to `backend_config()` | `tools/aws/_backend.py` |
| 2 | State key format: `{prefix}/{env}/{region}/{stack_id}.tfstate` when region provided | `tools/aws/_backend.py` |
| 3 | Add `--region` to `deploy.py`; pass region to all backend/tofu calls | `tools/aws/deploy.py` |
| 4 | Add `--region` to `teardown.py`; pass region to all backend/tofu calls | `tools/aws/teardown.py` |
| 5 | Add `--region` to `ensure_secrets.py`, `build_and_push_images.py`, `kube_apply.py`, `doctor.py` (or accept from env) | Various |
| 6 | Create `migrate_state_to_region_key.py` | `tools/aws/migrate_state_to_region_key.py` |
| 7 | Set `CLOUD_REGION`/`AWS_REGION` in tofu env when running Terraform (so provider uses correct region) | `get_tofu_env()` or callers |
| 8 | Update `get_base_vars()` / `_aws_vars` to use region for `aws_region` TF var | `tools/aws/_aws_vars.py` |
| 9 | Document `AWS_REGION` in `.env.example` | `.env.example` or `docs/` |

### migrate_state_to_region_key.py

**Purpose**: One-time migration of existing Terraform state from old key to new region-scoped key.

**Behavior**:

- `--dry-run`: List S3 objects that would be copied; show old key → new key mapping
- `--execute`: Copy state objects in S3 from `{prefix}/{env}/{stack_id}.tfstate` to `{prefix}/{env}/{region}/{stack_id}.tfstate`
- Stacks: shared/durable, shared/nondurable, kube, nonkube (all that exist)
- Use `aws s3 cp` or boto3; preserve metadata
- After copy, old objects can be deleted manually (or with `--delete-old` flag, optional)

**Usage**:

```bash
python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --dry-run
python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --execute
```

---

## 5. Migration Flow

### For Existing Deployments (already using Plan 1)

1. **Before Plan 2**: State at `fru/dev/aws-shared-durable.tfstate`, etc.
2. **Run migration**:
   ```bash
   python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --dry-run
   python tools/aws/migrate_state_to_region_key.py --env dev --region us-east-1 --execute
   ```
3. **After migration**: State at `fru/dev/us-east-1/aws-shared-durable.tfstate`, etc.
4. **Deploy/teardown** must use `--region us-east-1` (or `CLOUD_REGION=us-east-1`).

### For New Deployments (after Plan 2)

- No migration needed. First deploy uses region-scoped keys directly.
- `python tools/aws/deploy.py --scope nonkube --env dev --region us-west-2` creates state at `fru/dev/us-west-2/...`.

---

## 6. Multi-Region Config

### .env Additions

```bash
# AWS region (used by provider and when --region not passed)
CLOUD_REGION=us-east-1
```

### Per-Region Considerations

- **ECR**: Replicated or per-region? Legacy often uses single-region ECR; images are pulled cross-region. For true multi-region, consider ECR replication or per-region repos.
- **Secrets Manager**: Secrets are region-scoped. Each region needs its own secrets (or use cross-region replication).
- **S3 state bucket**: Can be in one region; state keys include region for isolation.
- **Aurora, VPC, EKS, ECS**: All region-specific. Each region has its own stacks.

### Remote State References

Stacks that use `terraform_remote_state` (e.g. kube, nonkube reading shared_durable) must reference the **same region** for shared stacks. The backend key includes region, so `data.terraform_remote_state.shared_durable` in kube must point to `fru/dev/us-east-1/aws-shared-durable.tfstate` when deploying to us-east-1.

**Implementation**: `backend_config` already builds the key. As long as deploy/teardown pass the same `region` for all stacks in a single run, remote state references stay consistent.

---

## 7. References

- [FINAL_REFACTOR_PLAN.md](./FINAL_REFACTOR_PLAN.md) – Prerequisite; Phase 5 (Aurora + DB wiring)
- [FINAL_REFACTOR_PLAN.md § 4.2 Multi-Region](./FINAL_REFACTOR_PLAN.md#42-multi-region) – Design context
- `tools/aws/_backend.py` – Backend config
- `tools/aws/deploy.py` – Deploy orchestrator
- `tools/aws/teardown.py` – Teardown orchestrator
