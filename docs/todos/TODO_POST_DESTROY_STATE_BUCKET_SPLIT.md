# Refactor Plan: Decompose post_destroy_durable_orphans into Two Functions

## Goal

Only delete the state bucket and lock table when `--incl-dura-all` is set (full teardown). When `--incl-dura` only, keep the bucket and lock table because `durable_with_cooloff` (secrets) was not destroyed and its state lives in the bucket.

**Approach:** Decompose into two focused functions, called individually by the teardown orchestrator.

## Target Behavior

| Component | --incl-dura | --incl-dura-all |
|:----------|:------------|:----------------|
| RDS log group | Delete | Delete |
| ECS log group | Delete | Delete |
| State bucket | **Keep** | Delete |
| Lock table | **Keep** | Delete |

## New Structure

### Function 1: `post_destroy_durable_log_groups`

**Responsibility:** Remove CloudWatch log groups that AWS creates as side effects of RDS/ECS. These are always orphaned when durable is destroyed.

**Resources:**
- RDS log group: `/aws/rds/cluster/{proj}-{env}-aurora-cluster/postgresql`
- ECS Container Insights log group: `/aws/ecs/containerinsights/{proj}-{env}-cluster/performance`

**Called when:** `(args.incl_dura or args.incl_dura_all) and args.scope == "all"`

### Function 2: `post_destroy_state_backend`

**Responsibility:** Remove the Terraform state bucket and DynamoDB lock table. Only safe when `durable_with_cooloff` is also destroyed (full teardown), since that stack's state lives in the bucket.

**Resources:**
- S3 state bucket (created by setup_state_backend.py)
- DynamoDB lock table (if configured)

**Called when:** `args.incl_dura_all and args.scope == "all"`

### Deprecate: `post_destroy_durable_orphans`

Keep as a thin wrapper that calls both functions (for backward compatibility during migration), or remove and update all callers.

## Implementation Steps

### 1. Create `post_destroy_durable_log_groups` in durable_post_destroy.py

Extract the RDS and ECS log group logic into a new function:

```python
def post_destroy_durable_log_groups(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """Remove RDS and ECS CloudWatch log groups orphaned when durable is destroyed."""
```

### 2. Create `post_destroy_state_backend` in durable_post_destroy.py

Extract the state bucket and lock table logic into a new function:

```python
def post_destroy_state_backend(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """Remove state bucket and lock table. Call only when durable_with_cooloff was destroyed (--incl-dura-all)."""
```

### 3. Refactor durable_post_destroy.py layout

**Option A (recommended):** Replace `post_destroy_durable_orphans` body with two calls:

```python
def post_destroy_durable_orphans(env, region, stats=None):
    """Legacy: runs both log groups and state backend. Prefer calling the two functions directly."""
    post_destroy_durable_log_groups(env, region, stats)
    post_destroy_state_backend(env, region, stats)
```

**Option B:** Remove `post_destroy_durable_orphans` entirely and update the single caller.

### 4. Update teardown.py caller

**File:** `tools/aws/teardown.py`

```python
# Post-destroy: when durable was destroyed, remove orphans
if (args.incl_dura or args.incl_dura_all) and args.scope == "all":
    logger.step("Post-destroy: removing durable orphans (log groups)...")
    try:
        post_destroy_durable_log_groups(args.env, region, stats=stats)
    except Exception as e:
        logger.warning(f"Post-destroy durable log groups: {e}")

    if args.incl_dura_all:
        logger.step("Post-destroy: removing state backend (bucket, lock table)...")
        try:
            post_destroy_state_backend(args.env, region, stats=stats)
        except Exception as e:
            logger.warning(f"Post-destroy state backend: {e}")

    # Remove local Docker cache images...
```

### 5. Update imports in teardown.py

```python
from tools.aws.scope_shared.teardown.durable_post_destroy import (
    post_destroy_durable_log_groups,
    post_destroy_state_backend,
)
```

### 6. Update durable_post_destroy.py module docstring

Document the two functions, when each is called, and the rationale for the split.

### 7. Optional: GCP parity

If GCP has equivalent post-destroy logic, apply the same decomposition there.

## File Layout After Refactor

```
tools/aws/scope_shared/teardown/durable_post_destroy.py
├── post_destroy_durable_log_groups(env, region, stats)   # RDS + ECS log groups
├── post_destroy_state_backend(env, region, stats)        # bucket + lock table
└── post_destroy_durable_orphans(env, region, stats)     # optional: calls both (legacy)
```

## Rationale for Decomposition

- **Single responsibility:** Each function has one clear purpose.
- **Explicit call sites:** Teardown orchestrator explicitly chooses which to run; no hidden conditionals.
- **Testability:** Each function can be tested in isolation.
- **Documentation:** Function names and docstrings make the split self-explanatory.
