# Refactor Plan: Dynamic Naming (Prefix-Only .env)

## 1. Problem

`.env` contains hardcoded resource names with `dev` baked in:

| Current (.env) | Issue |
|----------------|-------|
| `S3_DELTA_BUCKET=fru-dev-delta-internal` | Locks env to `dev` |
| `S3_ARTIFACT_BUCKET=fru-dev-artifacts-internal` | Same |
| `ECR_REPO_APP=fru-dev-api` | Same |
| `ECR_REPO_SPARK=fru-dev-spark` | Same |
| `CLOUDWATCH_LOG_GROUP=/fru/dev/spark` | Same |
| `EKS_CLUSTER_NAME=fru-dev-eks` | Same |
| `ECS_CLUSTER_NAME=fru-dev-ecs` | Same |

**Desired:** Convert each var to a `*_PREFIX` that contains **no** `env`, `region`, or `scope`. Those dimensions are appended dynamically at runtime from CLI/code.

---

## 2. Suitability & Feasibility

### 2.1 Suitability — ✅ High

| Criterion | Assessment |
|-----------|------------|
| **Single source of truth** | CLI args (`--env`, `--region`, `--scope`) drive all names; no .env override with full names |
| **Multi-env** | `deploy --env prod` and `deploy --env dev` use different resources without .env changes |
| **Multi-region** | `--region us-east-2` vs `us-east-1` already partially supported; naming should be consistent |
| **Consistency** | Matches `TF_STATE_BUCKET_PREFIX` / `TF_LOCK_TABLE_PREFIX` pattern already in use |

### 2.2 Feasibility — ✅ High

| Factor | Status |
|--------|--------|
| **Existing fallback logic** | `terra_var_handling.py` already computes `f"{prefix}-{env}-delta"` when `S3_DELTA_BUCKET` is unset |
| **CLI args flow** | Orchestrator passes `--env`, `--region`; deploy passes `--scope`; tools receive them |
| **Dimension awareness** | `scope` (kube/nonkube) and `region` are known at deploy time from stack path and args |
| **Migration** | Remove overrides from .env; existing compute logic becomes the only path |

### 2.3 Risk — ⚠️ Migration

- **Existing resources** with names like `fru-dev-delta-internal` will not match new computed names (e.g. `fru-delta-dev-us-east-1`).
- **Options:** (a) Adopt new naming and teardown/redeploy, or (b) Keep current pattern `{prefix}-{env}-{component}` (no reorder) and only remove .env overrides so `env` comes from CLI.

---

## 3. Naming Convention

### 3.1 Current vs Proposed

| Resource | Current pattern | Proposed (values at end) |
|----------|-----------------|---------------------------|
| Delta bucket | `{prefix}-{env}-delta-{region}` | `{prefix}-delta-{env}-{region}` |
| Artifacts bucket | `{prefix}-{env}-artifacts-{region}` | `{prefix}-artifacts-{env}-{region}` |
| ECR app | `{prefix}-{env}-api-{region}` | `{prefix}-api-{env}-{region}` |
| ECR spark | `{prefix}-{env}-spark-{region}` | `{prefix}-spark-{env}-{region}` |
| EKS cluster | `{prefix}-{env}-eks` | `{prefix}-eks-{env}-{region}` |
| ECS cluster | `{prefix}-{env}-ecs` | `{prefix}-ecs-{env}-{region}` |
| CloudWatch log | `/fru/{env}/spark` | `/{prefix}/{env}/{region}/spark` or `/{prefix}/spark/{env}-{region}` |

**Scope** (kube/nonkube) is already in component names where it matters (e.g. frontend: `{prefix}-{env}-frontend-{suffix}-{region}` with suffix=kube|nonkube).

### 3.2 Recommendation

- **Minimal change:** Keep `{prefix}-{env}-{component}-{region}` (current). Only remove .env overrides so `env` and `region` come from CLI. No name reorder.
- **Full change:** Switch to `{prefix}-{component}-{env}-{region}` (values at end). Requires Terraform and tool updates; existing resources must be recreated.

---

## 4. Refactor Plan (Minimal — Remove .env Overrides)

### Phase 0: Ensure env/region flow from CLI

| Task | Description |
|------|-------------|
| 0.1 | In `deploy.py`, `teardown.py`: at entry, set `os.environ["FRU_ENV"] = args.env` and `os.environ["CLOUD_REGION"] = region` |
| 0.2 | In `orchestrator.py`: pass `--env` and `--region`; ensure `FRU_ENV` is set before subprocess (or pass via env) |
| 0.3 | Audit `backend.py` `resolve_state_bucket`: it uses `FRU_ENV`; ensure deploy sets it before any backend call |

### Phase 1: Convert to `*_PREFIX` vars in .env

Replace full-name vars with PREFIX vars. The PREFIX must **not** contain `env`, `region`, or `scope`; those are appended dynamically.

| Current (.env) | Convert to | Full name at runtime |
|----------------|------------|----------------------|
| `S3_DELTA_BUCKET=fru-dev-delta-internal` | `S3_DELTA_BUCKET_PREFIX=fru-delta` | `{prefix}-{env}-{region}` → `fru-delta-dev-us-east-1` |
| `S3_ARTIFACT_BUCKET=fru-dev-artifacts-internal` | `S3_ARTIFACT_BUCKET_PREFIX=fru-artifacts` | `{prefix}-{env}-{region}` |
| `ECR_REPO_APP=fru-dev-api` | `ECR_REPO_APP_PREFIX=fru-api` | `{prefix}-{env}-{region}` |
| `ECR_REPO_SPARK=fru-dev-spark` | `ECR_REPO_SPARK_PREFIX=fru-spark` | `{prefix}-{env}-{region}` |
| `EKS_CLUSTER_NAME=fru-dev-eks` | `EKS_CLUSTER_NAME_PREFIX=fru-eks` | `{prefix}-{env}-{region}` |
| `ECS_CLUSTER_NAME=fru-dev-ecs` | `ECS_CLUSTER_NAME_PREFIX=fru-ecs` | `{prefix}-{env}-{region}` |
| `CLOUDWATCH_LOG_GROUP=/fru/dev/spark` | `CLOUDWATCH_LOG_GROUP_PREFIX=/fru` | `{prefix}/{env}/{region}/spark` or `{prefix}/spark/{env}-{region}` |

**Example .env after conversion:**
```bash
# PREFIX only — no env, region, or scope
S3_DELTA_BUCKET_PREFIX=fru-delta
S3_ARTIFACT_BUCKET_PREFIX=fru-artifacts
ECR_REPO_APP_PREFIX=fru-api
ECR_REPO_SPARK_PREFIX=fru-spark
EKS_CLUSTER_NAME_PREFIX=fru-eks
ECS_CLUSTER_NAME_PREFIX=fru-ecs
CLOUDWATCH_LOG_GROUP_PREFIX=/fru
```

**Optional suffix:** If you need `-internal` (e.g. for private buckets), include it in the PREFIX: `S3_DELTA_BUCKET_PREFIX=fru-delta-internal` → full = `fru-delta-internal-dev-us-east-1`. The PREFIX is everything before `{env}`.

### Phase 2: Centralize name resolution

| Task | Description |
|------|-------------|
| 2.1 | Create naming helper that reads `*_PREFIX` from env and appends `env`, `region`, `scope`: |
| | `delta_bucket = os.getenv("S3_DELTA_BUCKET_PREFIX", "fru-delta") + f"-{env}-{region}"` |
| | Or: `resource_name(prefix_env_key, env, region, scope=None) -> str` |
| 2.2 | Update `terra_var_handling.py`: read `S3_DELTA_BUCKET_PREFIX` etc.; build full names by appending `-{env}-{region}` |
| 2.3 | Update `doctor.py`: use `*_PREFIX` + env + region; remove checks for full-name vars |

### Phase 3: Update all consumers

| Task | Description |
|------|-------------|
| 3.1 | `kube_apply.py`, `deploy_kube.py`, `bootstrap_helpers.py`, `deploy_common.py`, `teardown.py`, `verify_*`, `eks_kubeconfig.py` |
| | Replace `os.getenv("EKS_CLUSTER_NAME")` with `os.getenv("EKS_CLUSTER_NAME_PREFIX", "fru-eks") + f"-{env}-{region}"` (or naming helper) |
| 3.2 | Ensure `env` and `region` are always passed (from deploy/teardown args) into these code paths |

### Phase 4: Backward compatibility (optional)

| Task | Description |
|------|-------------|
| 4.1 | Support **legacy** full-name vars (`S3_DELTA_BUCKET`, etc.) as overrides when set — use them instead of building from `*_PREFIX` |
| 4.2 | Prefer `*_PREFIX` when both exist; deprecate full-name vars |

---

## 5. Refactor Plan (Full — Values at End)

If you adopt `{prefix}-{component}-{env}-{region}`:

| Task | Description |
|------|-------------|
| 5.1 | Implement naming helper with new order |
| 5.2 | Update Terraform modules: change `var.delta_bucket` construction; update all `"${var.prefix}-${var.env}-*"` to `"${var.prefix}-*-${var.env}-${var.aws_region}"` |
| 5.3 | **Migration:** Teardown existing stacks; deploy with new names. Or use Terraform `moved` blocks if names can be migrated in-place (usually not for S3/ECR). |

---

## 6. Summary

**Conversion rule:** Each full-name var becomes a `*_PREFIX` var. The PREFIX has no `env`, `region`, or `scope`; those are appended at runtime.

| .env (before) | .env (after) | Runtime (e.g. env=dev, region=us-east-1) |
|---------------|--------------|------------------------------------------|
| `S3_DELTA_BUCKET=fru-dev-delta-internal` | `S3_DELTA_BUCKET_PREFIX=fru-delta` | `fru-delta-dev-us-east-1` |
| `EKS_CLUSTER_NAME=fru-dev-eks` | `EKS_CLUSTER_NAME_PREFIX=fru-eks` | `fru-eks-dev-us-east-1` |

| Approach | Effort | Migration |
|----------|--------|-----------|
| **Convert to *_PREFIX** (Phases 0–4) | Medium | New names; teardown/redeploy if existing resources differ |
| **Full** (values at end: `{prefix}-{component}-{env}-{region}`) | Medium–High | Same as above |
