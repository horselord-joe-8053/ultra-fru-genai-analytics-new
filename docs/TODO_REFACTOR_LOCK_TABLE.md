# Refactor Plan: Use Fix A (Bootstrap region), Remove `-lock=false`

## Goal

Adopt **Fix A: Bootstrap region** consistently and remove all `-lock=false` usage from the codebase. Documentation (e.g. `docs/learned/terra/TERRA_DYNAMODB_LOCK_TABLE.md`) remains unchanged.

---

## Prerequisite

**Bootstrap creates the lock table in the correct region.**  
`setup_state_backend.py` already passes `--region` to `aws dynamodb` commands. No change needed.

---

## Files to Change (Code Only)

### 1. Core Terra Runners (Remove Automatic `-lock=false`)

| File | Change |
|------|--------|
| `tools/aws/scope_shared/core/terra_runner.py` | Remove the logic in `terra_capture()` (lines 78–80) and `terra()` (lines 95–98) that injects `-lock=false` for init, plan, apply, destroy, output, import. |
| `tools/gcp/scope_shared/core/terra_runner.py` | Same change as AWS. |

### 2. Init Logic (Remove `-lock=false` from Init Args)

| File | Change |
|------|--------|
| `tools/aws/scope_shared/core/terra_init.py` | Change `args = ["init", "-lock=false", "-upgrade", "-reconfigure"]` to `args = ["init", "-upgrade", "-reconfigure"]`. |
| `tools/gcp/scope_shared/core/terra_init.py` | Same change. |
| `tools/aws/scope_shared/deploy/setup_database.py` | Remove `-lock=false` from init args. |
| `tools/aws/scope_shared/verify/verify_db_password.py` | Remove `-lock=false` from init args. |
| `tools/cloud_shared/ensure_secrets.py` | Remove `-lock=false` from init args (both occurrences). |
| `tools/gcp/scope_shared/deploy/db_setup/config.py` | Remove `-lock=false` from init args. |

### 3. Import Commands (Remove `-lock=false`)

| File | Change |
|------|--------|
| `tools/aws/scope_shared/deploy/deploy_common.py` | Remove `-lock=false` from the import command in `apply_stack_nonkube_with_ecs_import_retry()`. |
| `tools/aws/scope_shared/import_preexist/_common.py` | Remove `-lock=false` from the import command. |

### 4. Destroy Command

| File | Change |
|------|--------|
| `tools/aws/teardown.py` | Remove `-lock=false` from the destroy command. |

### 5. Refresh Command

| File | Change |
|------|--------|
| `tools/aws/standalone/restore_durable_state.py` | Remove `-lock=false` from the refresh command. |

---

## Execution Order

1. **Phase 1 – Core runners**  
   Update `terra_runner.py` (AWS and GCP) so they no longer add `-lock=false`.

2. **Phase 2 – Init**  
   Update all init call sites (terra_init, setup_database, verify_db_password, ensure_secrets, GCP db_setup).

3. **Phase 3 – Import**  
   Update deploy_common and import_preexist.

4. **Phase 4 – Destroy and refresh**  
   Update teardown and restore_durable_state.

---

## Dependency and Ordering

- **Deploy:** Phase 2 runs `setup_state_backend` before any tofu commands, so the lock table exists before init/apply.
- **Teardown:** Assumes a prior deploy (or manual bootstrap), so the table should already exist.
- **Standalone scripts** (restore_durable_state, setup_database, verify_db_password, ensure_secrets):  
  - Either run after deploy (which runs bootstrap), or  
  - Require a prior manual run of bootstrap.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Lock table missing in a region | Bootstrap must be run first (deploy does this). Document that manual tofu use requires bootstrap. |
| Concurrent tofu runs | Using the lock table protects against concurrent state writes. |
| GCP backend | GCP uses GCS backend with its own locking; removing `-lock=false` is consistent and should be safe. |

---

## Verification

1. Run full deploy: `CLOUD_REGION=us-east-2 python tools/aws/deploy.py --scope all --env dev --region us-east-2`.
2. Run teardown (if desired).
3. Run `tofu state rm` manually (after bootstrap) and confirm it uses the lock table.
4. Run `restore_durable_state.py` (after bootstrap) and confirm refresh works.
