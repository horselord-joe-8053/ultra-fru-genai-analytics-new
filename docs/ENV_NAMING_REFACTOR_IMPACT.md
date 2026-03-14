# Env Naming Convention Refactor Plan

**Purpose:** Refactor remaining env vars to follow `<proj_prefix>-<component>-<env>...` convention.  
**Reference:** `docs/ENV_NAMING_ALIGNMENT.md` (inventory), `docs/STEP_LARGE_REFACTOR_RENAMING.md` (convention).

**When to use:** Execute phases in order when ready to align env vars with naming convention.

---

## Summary

| Env Var | Risk | Effort | Phase |
|---------|------|--------|-------|
| `CLOUDWATCH_LOG_GROUP` | Low | 1–2 files | 1 |
| `EKS_CLUSTER_NAME`, `ECS_CLUSTER_NAME` | Low | .env only | 1 |
| `K8S_NAMESPACE` | Moderate | 4–6 files | 2 |
| `PGDATABASE` | High | 10+ files | 3 |
| `DELTA_TABLE_PATH` | High | 8+ files | 4 |

**Principle:** Derive values from components; keep built values same as current (e.g. `fru_db`, `fru_sales`) to avoid DB/data migration.

---

## Phase 1: Low-Risk (1–2 hours)

### 1.1 CLOUDWATCH_LOG_GROUP

**Files to edit:**
- `.env` — Remove or comment out `CLOUDWATCH_LOG_GROUP=/fru/dev/spark`
- `.env.example` — Remove or comment out
- `tools/aws/scope_shared/deploy/k8s_deploy_helpers.py` — Line ~35: change
  ```python
  lg = log_group or os.getenv("CLOUDWATCH_LOG_GROUP") or resource_names.log_group_spark(env, region)
  ```
  to
  ```python
  lg = log_group or resource_names.log_group_spark(env, region)
  ```

**Verification:** `check_ecs_bootstrap_succeeded` / verify deploy; log group path = `/{proj}/cloud-log-group-spark/{env}/{region}`

### 1.2 EKS_CLUSTER_NAME, ECS_CLUSTER_NAME

**Files to edit:**
- `.env` — Remove or comment out `EKS_CLUSTER_NAME=fru-dev-eks` and `ECS_CLUSTER_NAME=fru-dev-ecs`
- `.env.example` — Remove or comment out (if present)

**Code changes:** None. `resource_names._component()` already uses `EKS_CLUSTER_COMPONENT` / `ECS_CLUSTER_COMPONENT` when legacy vars unset. `terra_var_handling` still sets `EKS_CLUSTER_NAME` at runtime for eks_kubeconfig.

**Verification:** Doctor, deploy plan, kube apply

---

## Phase 2: K8S_NAMESPACE (2–4 hours)

**Target:** Add `K8S_NAMESPACE_COMPONENT=kube`; build `{PROJ_PREFIX}-{component}` at runtime.

### 2.1 .env

Add:
```
K8S_NAMESPACE_COMPONENT=kube
```
Keep `K8S_NAMESPACE=fru-kube` as optional override during transition (can remove after verification).

### 2.2 Shared helper

**Option A:** Add to `tools/cloud_shared/resource_names.py` (create if needed):
```python
def k8s_namespace() -> str:
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    comp = os.getenv("K8S_NAMESPACE_COMPONENT", "").strip() or "kube"
    return os.getenv("K8S_NAMESPACE", "").strip() or f"{proj}-{comp}"
```

**Option B:** Add `k8s_namespace()` to both `tools/aws/scope_shared/core/resource_names.py` and `tools/gcp/scope_shared/core/resource_names.py` with same logic.

### 2.3 Files to update

| File | Change |
|------|--------|
| `tools/aws/scope_shared/deploy/k8s_deploy_helpers.py` | Replace `K8S_NAMESPACE = "fru-kube"` with import and use `resource_names.k8s_namespace()` (or cloud_shared). Update all references. |
| `tools/aws/kube/kube_apply.py` | Import `k8s_namespace` from resource_names; use instead of `K8S_NAMESPACE` |
| `tools/aws/kube/kube_pre_destroy.py` | Same |
| `tools/aws/kube/deploy_kube.py` | Same |
| `tools/aws/scope_shared/verify/verify_all_teardown.py` | Same |
| `tools/aws/scope_shared/verify/verify_all_deploy.py` | Same |
| `tools/aws/deploy.py` | Update import if needed |
| `tools/gcp/scope_shared/core/resource_names.py` | Update `k8s_namespace()` to build from `K8S_NAMESPACE_COMPONENT`; keep `K8S_NAMESPACE` as override |
| `tools/gcp/scope_shared/verify/verify_all_teardown.py` | Already uses `k8s_namespace()`; ensure it uses updated implementation |

**Verification:** Kube deploy, pre-destroy, verify teardown; namespace = `fru-kube` (unchanged)

---

## Phase 3: PGDATABASE (4–8 hours)

**Target:** Add `PG_DATABASE_COMPONENT=db`; build `{PROJ_PREFIX}_{component}` = `fru_db`; pass to Terraform and containers.

### 3.1 .env

Add:
```
PG_DATABASE_COMPONENT=db
```
Keep `PGDATABASE=fru_db` in COMMON section for local dev (app reads it).

### 3.2 Add pg_database_name()

**AWS** `tools/aws/scope_shared/core/resource_names.py`:
```python
def pg_database_name() -> str:
    proj = _proj_prefix()
    comp = os.getenv("PG_DATABASE_COMPONENT", "").strip() or "db"
    return f"{proj}_{comp}"
```

**GCP** `tools/gcp/scope_shared/core/resource_names.py`:
```python
def pg_database_name() -> str:
    proj = _proj_prefix()
    comp = os.getenv("PG_DATABASE_COMPONENT", "").strip() or "db"
    return f"{proj}_{comp}"
```

### 3.3 Terraform

| File | Change |
|------|--------|
| `infra_terraform/live_deploy/aws/scope_shared/durable/variables.tf` | Variable `aurora_database_name` already exists with default `"fru_db"`. Deploy must pass `-var=aurora_database_name=...` from `pg_database_name()`. |
| `infra_terraform/live_deploy/gcp/scope_shared/durable/variables.tf` | Variable `cloud_sql_database_name` already exists with default `"fru_db"`. Deploy must pass `-var=cloud_sql_database_name=...` from `pg_database_name()`. |

### 3.4 Deploy scripts

| File | Change |
|------|--------|
| `tools/aws/scope_shared/core/terra_var_handling.py` | Add `set_tf("aurora_database_name", resource_names.pg_database_name())` if durable stack is initialized from here; or ensure deploy passes it. |
| `tools/gcp/deploy.py` | In durable stack plan_vars, add `f"-var=cloud_sql_database_name={pg_database_name()}"` (add helper or import from cloud_shared). |
| `tools/aws/kube/kube_apply.py` | `--pg-database` default: use `resource_names.pg_database_name()` instead of `"fru_db"` |
| `tools/aws/kube/deploy_kube.py` | Fallback: use `resource_names.pg_database_name()` instead of `"fru_db"` |
| `tools/aws/scope_shared/deploy/setup_database.py` | Fallback: use `resource_names.pg_database_name()` |
| `tools/aws/scope_shared/verify/verify_db_password.py` | Fallback: use `resource_names.pg_database_name()` |

**Note:** AWS durable stack — check how `aurora_database_name` is passed (terra_var_handling vs deploy.py). GCP deploy.py explicitly builds plan_vars for durable.

**Verification:** Deploy durable, nonkube, kube; API connects to DB; setup_database succeeds

---

## Phase 4: DELTA_TABLE_PATH (4–8 hours)

**Target:** Add `DELTA_TABLE_COMPONENT=sales`; build table name `{proj}_{component}` = `fru_sales`; path = `{bucket}/delta/{table_name}`.

### 4.1 .env

Add:
```
DELTA_TABLE_COMPONENT=sales
```
Keep `DELTA_TABLE_PATH=data/delta/fru_sales` for local dev.

### 4.2 Add delta_table_name()

**AWS** `tools/aws/scope_shared/core/resource_names.py`:
```python
def delta_table_name() -> str:
    proj = _proj_prefix()
    comp = os.getenv("DELTA_TABLE_COMPONENT", "").strip() or "sales"
    return f"{proj}_{comp}"
```

**GCP** `tools/gcp/scope_shared/core/resource_names.py`:
```python
def delta_table_name() -> str:
    proj = _proj_prefix()
    comp = os.getenv("DELTA_TABLE_COMPONENT", "").strip() or "sales"
    return f"{proj}_{comp}"
```

### 4.3 Terraform

| File | Change |
|------|--------|
| `infra_terraform/live_deploy/aws/nonkube/variables.tf` | Add `variable "delta_table_name" { type = string }` (or use default from resource_names; Terraform cannot call Python, so deploy must pass it) |
| `infra_terraform/live_deploy/aws/nonkube/main.tf` | Change `s3a://${var.delta_bucket}/delta/fru_sales` to `s3a://${var.delta_bucket}/delta/${var.delta_table_name}` |
| `infra_terraform/live_deploy/gcp/nonkube/variables.tf` | Add `variable "delta_table_name" { type = string }` |
| `infra_terraform/live_deploy/gcp/nonkube/main.tf` | Change `gs://${local.delta_bucket}/delta/fru_sales` to `gs://${local.delta_bucket}/delta/${var.delta_table_name}`; add var to locals or pass through |
| `infra_terraform/modules/aws/ecs/main.tf` | If it has hardcoded path, add variable and pass from parent |

### 4.4 Deploy scripts

| File | Change |
|------|--------|
| `tools/aws/scope_shared/core/terra_var_handling.py` | Add `set_tf("delta_table_name", resource_names.delta_table_name())` if nonkube uses it; or ensure deploy passes `-var=delta_table_name=...` |
| `tools/gcp/deploy.py` | In nonkube plan_vars, add `f"-var=delta_table_name={delta_table_name()}"` |
| `tools/aws/kube/kube_apply.py` | Build path: `f"s3a://{delta_bucket}/delta/{resource_names.delta_table_name()}"` instead of hardcoded `fru_sales` |
| `tools/aws/kube/deploy_kube.py` | Same |
| `tools/aws/scope_shared/deploy/deploy_common.py` | `prefix = f"delta/{resource_names.delta_table_name()}/"` instead of `"delta/fru_sales/"` |

**Verification:** Spark job reads Delta table; bootstrap job; analytics scheduler

---

## Verification Checklist (All Phases)

After each phase:

- [ ] Doctor passes (AWS and/or GCP)
- [ ] `tofu plan` succeeds for affected stacks
- [ ] Deploy completes (or at least plan)
- [ ] Bootstrap job completes (kube)
- [ ] API connects to DB (PGDATABASE)
- [ ] Spark/analytics job reads Delta table
- [ ] Verify/teardown scripts work
- [ ] No new hardcoded `fru_db`, `fru_sales`, `fru-kube` in refactored paths

---

## File Change Summary

| Phase | Files |
|-------|-------|
| 1 | `.env`, `.env.example`, `k8s_deploy_helpers.py` |
| 2 | `.env`, `k8s_deploy_helpers.py`, `kube_apply.py`, `kube_pre_destroy.py`, `deploy_kube.py`, `verify_all_teardown.py` (AWS+GCP), `verify_all_deploy.py`, `deploy.py`, `resource_names.py` (AWS+GCP) |
| 3 | `.env`, `resource_names.py` (AWS+GCP), durable `variables.tf` (AWS+GCP), `terra_var_handling.py`, `deploy.py` (GCP), `kube_apply.py`, `deploy_kube.py`, `setup_database.py`, `verify_db_password.py` |
| 4 | `.env`, `resource_names.py` (AWS+GCP), nonkube `variables.tf` + `main.tf` (AWS+GCP), `ecs/main.tf`, `terra_var_handling.py`, `deploy.py` (GCP), `kube_apply.py`, `deploy_kube.py`, `deploy_common.py` |

---

## Rollback

If issues arise:
- Phase 1: Re-add `CLOUDWATCH_LOG_GROUP`, `EKS_CLUSTER_NAME`, `ECS_CLUSTER_NAME` to `.env`; revert `k8s_deploy_helpers.py`
- Phase 2: Re-add `K8S_NAMESPACE=fru-kube`; revert `k8s_deploy_helpers` and callers to use constant
- Phase 3: Remove `-var=aurora_database_name` / `-var=cloud_sql_database_name` from deploy; Terraform defaults remain `fru_db`
- Phase 4: Remove `-var=delta_table_name`; revert Terraform to hardcoded `fru_sales`
