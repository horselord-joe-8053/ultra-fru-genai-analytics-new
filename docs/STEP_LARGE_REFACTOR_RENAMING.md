# Final Refactor Plan: Project Prefix vs Component Prefix (.env Renaming)

**Purpose:** Adopt the naming convention with clear separation of `<project_prefix>` and `<component_prefix>`, and refactor `.env` vars to hold only the appropriate part. This document is the refactor plan for the renaming phase.

**Related:** `docs/war_stories/WAR_STORIES_AWS.md` §39 (path-style naming).

---

## Part A: Naming Convention (Full Enhanced Convention)

We use two formats. **Both follow the same logical structure**; only the separator differs (`-` vs `/`).

### A.1 Full Pattern (All Segments)

| Format | Full pattern |
|--------|--------------|
| **Hyphen-style** | `<project_prefix>-<component_prefix>-<other component info>-<env>-<region, if region-specific and not shared>-<scope, if scope-specific and not shared>-<random ID if necessary>` |
| **Path-style** | `<project_prefix>/<component_prefix>/<other component info>/<env>/<region, if region-specific and not shared>/<scope, if scope-specific and not shared>/<random ID if necessary>` |

**Optional segments** are omitted when not applicable (e.g. region when shared, scope when shared, random ID when not needed).

**Path-style** is used only for **Secrets Manager** and **CloudWatch Log Groups** (see War Story 65). All other resources use hyphen-style.

### A.2 Key Distinction

- **`<project_prefix>`** — Identifies the project (e.g. `fru`). Single value for the whole project.
- **`<component_prefix>`** — Identifies the resource type/component (e.g. `delta`, `eks`, `cloud-log-group-spark`). One per resource kind.

---

## Part B: Refactor 1 — Rename FRU_PREFIX to PROJ_PREFIX

| Before | After | Notes |
|--------|-------|-------|
| `FRU_PREFIX=fru` | `PROJ_PREFIX=fru` | Carries `<project_prefix>` only |

**Scope of change:**
- `.env`, `.env.example`
- All code that reads `FRU_PREFIX` or `os.getenv("FRU_PREFIX", "fru")`:
  - `terra_var_handling.py` (MAP, get_base_vars, defaults)
  - `backend.py` (stack key prefix)
  - `teardown.py`, `deploy_kube.py`, `kube_apply.py`, `verify_all_teardown.py`
  - `install_aws_load_balancer_controller.sh`, `install_aws_load_balancer_controller.py`
  - `doctor.py`, `scan_aws_remaining.py`, `split_buckets_even_for_regions.py`

**Safety:** Add backward compatibility: if `PROJ_PREFIX` is unset, fall back to `FRU_PREFIX` during a transition period. Remove fallback after migration.

---

## Part C: Refactor 2 — Component Prefix Vars

### C.1 Inventory: Current .env Vars and Their Intended Role

| .env var | Current value | Currently holds | Should hold (component_prefix) |
|----------|---------------|-----------------|--------------------------------|
| `FRU_PREFIX` | fru | project_prefix | → `PROJ_PREFIX` (Part B) |
| `IMAGE_PREFIX` | fru-api-img-default-prefix | Local Docker tag prefix | **Out of scope** — not AWS resource naming; keep as-is |
| `TF_STATE_BUCKET_PREFIX` | fru-tf-state | project+component (combined) | `TF_STATE_BUCKET_COMPONENT=tf-state` |
| `TF_LOCK_TABLE_PREFIX` | fru-tf-locks-tbl | project+component (combined) | `TF_LOCK_TABLE_COMPONENT=tf-locks-tbl` |
| `S3_DELTA_BUCKET` | fru-dev-delta-internal | Full name | `S3_DELTA_COMPONENT=delta-internal` |
| `S3_ARTIFACT_BUCKET` | fru-dev-artifacts-internal | Full name | `S3_ARTIFACT_COMPONENT=artifacts-internal` |
| `ECR_REPO_APP` | fru-dev-api | Full name | `ECR_APP_COMPONENT=api` |
| `ECR_REPO_SPARK` | fru-dev-spark | Full name | `ECR_SPARK_COMPONENT=spark` |
| `CLOUDWATCH_LOG_GROUP` | /fru/dev/spark | Full path (legacy) | `CLOUDWATCH_LOG_GROUP_SPARK=cloud-log-group-spark` (path-style; CloudWatch log group for spark) |
| `EKS_CLUSTER_NAME` | fru-dev-eks | Full name | `EKS_CLUSTER_COMPONENT=eks` |
| `ECS_CLUSTER_NAME` | fru-dev-ecs | Full name | `ECS_CLUSTER_COMPONENT=ecs` |
| `ALB_NAME` | (not in .env; default in code) | — | `ALB_COMPONENT=alb` (nonkube ALB; terra_var_handling default) |

### C.1a Thorough Inventory: All Resource-Naming Touchpoints

**In .env (explicit):** Above table.

**In code (defaults / derived):**
- `ALB_NAME` — `terra_var_handling.py` default `f"{prefix}-{env}-alb"` → add `ALB_COMPONENT=alb` for consistency.
- `TF_STATE_PREFIX` — `backend.py` uses for state key path; same as project prefix → use `PROJ_PREFIX`.

**In Terraform only (no .env):**
- **VPC, Aurora** — `var.prefix`, `var.env` from Terraform inputs (from `terra_var_handling`).
- **Secrets** — path-style in durable stack; `var.prefix`, `var.env`, secret key name.
- **Frontend S3, CloudFront, OAC** — per convention: `{prefix}-frontend-{env}-{region}-{scope}-{account_id}` → `fru-frontend-dev-us-east-1-kube-{account_id}` (scope = kube or nonkube). **Current Terraform** uses `{prefix}-{env}-frontend-{scope}-{region}` (non-compliant; env before component). Migration to convention order is a separate change. No .env component var.
- **EKS cluster** — kube stack; receives `eks_cluster_name` from TF vars (built by terra_var_handling).

**Excluded (not resource names):** `IMAGE_PREFIX`, `VPC_CIDR`, `CLOUD_REGION`, `FRU_ENV`, `FRU_TF_BIN`, credentials, etc.

### C.2 Proposed .env After Refactor (Component-Only Values)

```bash
# Project prefix (single value for whole project)
PROJ_PREFIX=fru

# Component prefixes — NO project prefix, NO env, NO region
TF_STATE_BUCKET_COMPONENT=tf-state
TF_LOCK_TABLE_COMPONENT=tf-locks-tbl
S3_DELTA_COMPONENT=delta-internal
S3_ARTIFACT_COMPONENT=artifacts-internal
ECR_APP_COMPONENT=api
ECR_SPARK_COMPONENT=spark
EKS_CLUSTER_COMPONENT=eks
ECS_CLUSTER_COMPONENT=ecs
ALB_COMPONENT=alb

# Path-style components (log groups; War Story 65)
CLOUDWATCH_LOG_GROUP_SPARK=cloud-log-group-spark
CLOUDWATCH_LOG_GROUP_ECS_API=ecs-api

# Out of scope (not resource naming)
IMAGE_PREFIX=fru-api-img-default-prefix
```

### C.3 Full Name Assembly (Runtime)

| Component | Hyphen-style full name | Path-style full name |
|-----------|------------------------|----------------------|
| TF state bucket | `{PROJ_PREFIX}-{TF_STATE_BUCKET_COMPONENT}-{env}-{region}-{account}` | N/A |
| TF lock table | `{PROJ_PREFIX}-{TF_LOCK_TABLE_COMPONENT}-{region}` | N/A |
| S3 delta | `{PROJ_PREFIX}-{S3_DELTA_COMPONENT}-{env}-{region}` | N/A |
| S3 artifacts | `{PROJ_PREFIX}-{S3_ARTIFACT_COMPONENT}-{env}-{region}` | N/A |
| ECR app | `{PROJ_PREFIX}-{ECR_APP_COMPONENT}-{env}-{region}` | N/A |
| ECR spark | `{PROJ_PREFIX}-{ECR_SPARK_COMPONENT}-{env}-{region}` | N/A |
| EKS cluster | `{PROJ_PREFIX}-{EKS_CLUSTER_COMPONENT}-{env}-{region}` | N/A |
| ECS cluster | `{PROJ_PREFIX}-{ECS_CLUSTER_COMPONENT}-{env}-{region}` | N/A |
| ALB (nonkube) | `{PROJ_PREFIX}-{ALB_COMPONENT}-{env}-{region}` | N/A |
| Log group (cloud-log-group-spark) | N/A | `/{PROJ_PREFIX}/{CLOUDWATCH_LOG_GROUP_SPARK}/{env}/{region}` |
| Log group (ecs-api) | N/A | `/{PROJ_PREFIX}/{CLOUDWATCH_LOG_GROUP_ECS_API}/{env}/{region}` |

**Note:** TF lock table currently omits `env` in the assembled name (`fru-tf-locks-tbl-us-east-1`). Preserve that behavior.

### C.4 Special Cases

**TF state bucket:** Backend also appends `{account_id}`. Full: `fru-tf-state-dev-us-east-1-{account}`.

**S3 delta/artifacts `-internal`:** The `-internal` suffix denotes private buckets. Including it in the component (`delta-internal`, `artifacts-internal`) keeps the full name correct: `fru-delta-internal-dev-us-east-1`.

**CLOUDWATCH_LOG_GROUP (verify):** `verify_all_deploy.py` checks the **spark** log group (bootstrap + batch analytics). Use `CLOUDWATCH_LOG_GROUP_SPARK=cloud-log-group-spark` — the value is more informative (CloudWatch log group for spark). Build full path: `/{PROJ_PREFIX}/cloud-log-group-spark/{env}/{region}` = `/fru/cloud-log-group-spark/dev/us-east-1`.

**IMAGE_PREFIX:** Used for local Docker image tags (e.g. `fru-api-img-default-prefix:latest`). Not an AWS resource name. **Do not change** — it serves a different purpose.

---

## Part D: Path-Style Names (Recap from War Story 65)

| Component | Example |
|-----------|---------|
| Log group (cloud-log-group-spark) | `/fru/cloud-log-group-spark/dev/us-east-1` |
| Log group (ecs-api) | `/fru/ecs-api/dev/us-east-1` |
| Secret | `/fru/secret/openai_api_key/dev/us-east-1` |

Terraform currently creates:
- `/fru/${var.env}/spark` → migrate to `/fru/cloud-log-group-spark/${var.env}/${var.aws_region}`
- `/fru/${var.env}/ecs-api` → migrate to `/fru/ecs-api/${var.env}/${var.aws_region}`

Secrets (durable) use path-style; naming is in Terraform vars, not .env.

---

## Part E: Code Impact Summary

| File | Changes |
|------|---------|
| `.env`, `.env.example` | Rename/add vars per Part B and C |
| `terra_var_handling.py` | `FRU_PREFIX`→`PROJ_PREFIX`; read `*_COMPONENT` vars; build full names via `resource_names.py` |
| `backend.py` | `FRU_PREFIX`→`PROJ_PREFIX`; `TF_STATE_BUCKET_PREFIX`→build from `PROJ_PREFIX`+`TF_STATE_BUCKET_COMPONENT`; same for lock table |
| `verify_all_deploy.py` | Build log group path from `PROJ_PREFIX`+`CLOUDWATCH_LOG_GROUP_SPARK`+env+region |
| `verify_all_teardown.py` | Build ECS cluster name from `PROJ_PREFIX`+`ECS_CLUSTER_COMPONENT`+env |
| `teardown.py` | Same for ECS/EKS cluster names |
| `deploy_kube.py`, `kube_apply.py` | Same for EKS cluster |
| `doctor.py` | Require `PROJ_PREFIX` and `*_COMPONENT` vars; remove full-name checks |
| `scan/config.py`, `orphan_rules.py` | Update patterns for new naming (prefix-component-env-region) |
| Terraform modules (ECS, etc.) | Update log group names to path-style; receive `prefix` (project) and component from vars |
| **`tools/aws/scope_shared/teardown/durable_post_destroy.py`** | **Review and refactor:** RDS log group, ECS log group, state bucket, lock table names are built from `FRU_PREFIX`, `env`, and backend resolvers. Update to use `PROJ_PREFIX` and `*_COMPONENT` vars (or `resource_names.py`) where suitable. |

---

## Part F: Migration Order

1. **Teardown** (current .env, all regions, scope=all, --incl-dura)
2. **Verify teardown**
3. **Resource scan → remove orphans**
4. **Update .env:** Rename `FRU_PREFIX` → `PROJ_PREFIX`; replace full-name vars with `*_COMPONENT` vars (Part C.2)
5. **Implement code changes** (Part E)
6. **Deploy** (new .env, all regions, scope=all)
7. **Resource scan → remove orphans**

---

## Part G: Backward Compatibility (Transition)

| Phase | Behavior |
|-------|----------|
| **During migration** | Support both: `PROJ_PREFIX` or fallback to `FRU_PREFIX`; support legacy full-name vars when `*_COMPONENT` unset |
| **After migration** | Remove `FRU_PREFIX` fallback; require `*_COMPONENT`; deprecate full-name vars |

---

## Part H: Summary

| Refactor | Before | After |
|----------|---------|-------|
| Project prefix | `FRU_PREFIX=fru` | `PROJ_PREFIX=fru` |
| Component vars | Full names or combined prefixes | `*_COMPONENT` vars with component only |
| Name assembly | Ad-hoc in each file | Centralized `resource_names.py` (Part I): single implementation of full enhanced convention (Part A.1); handles both hyphen and path via `style=` |
| Path-style | `/fru/dev/spark` | `/fru/cloud-log-group-spark/dev/us-east-1` |

**Out of scope:** `IMAGE_PREFIX` (local Docker); `VPC_CIDR` (not a resource name).

---

## Part I: resource_names.py — DRY and Dual-Format Support

**Principle:** `resource_names.py` is the **single place** that assembles full resource names. It must handle both hyphen-style and path-style with **no duplication** of the logical structure.

### I.1 Design

- **One internal representation** of the convention: `(project_prefix, component_prefix, other, env, region, scope, random_id)`.
- **Two output formatters:** `_hyphen(...)` and `_path(...)`, differing only in separator.
- **Public API:** `resource_name(component, env, region, scope=None, other=None, random_id=None, style="hyphen")` and `resource_name_path(...)` or `resource_name(..., style="path")`.

### I.2 DRY Rule

The full enhanced convention is implemented **once** in `resource_names.py`. All optional-segment logic (omit region when shared, omit scope when shared, etc.) lives in this module. Callers pass `env`, `region`, `scope`; the module decides which segments to include based on component type.

**Example (pseudocode):**
```python
def _segments(proj, comp, other, env, region, scope, random_id, *, include_region, include_scope):
    parts = [proj, comp]
    if other: parts.append(other)
    parts.extend([env])
    if include_region: parts.append(region)
    if include_scope: parts.append(scope)
    if random_id: parts.append(random_id)
    return parts

def resource_name(component, env, region, ..., style="hyphen"):
    segs = _segments(...)
    sep = "-" if style == "hyphen" else "/"
    return sep.join(segs)
```
