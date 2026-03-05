# Refactor Completed: Consolidate AWS/GCP (Phase 1–4)

**Branch:** `refactor/consolidate-aws-gcp`  
**Reference:** `tmp/TO_CONSOLIDATE_AWS_GCP.md` (analysis and plan)

---

## Summary of Changes

### Phase 1: Orchestrator + Verify

| Change | Files |
|--------|-------|
| Unified `handle_aws` and `handle_gcp` into `_handle_provider(args, base_path, provider, deploy_extra_before)` | `orchestrator.py` |
| Created `verify_all_deploy_common.run_verify_all_deploy()` with provider adapters | `tools/cloud_shared/verify/verify_all_deploy_common.py` |
| Refactored AWS/GCP `verify_all_deploy.py` to use common | `tools/aws/.../verify_all_deploy.py`, `tools/gcp/.../verify_all_deploy.py` |
| Created `verify_all_teardown_common.run_verify_all_teardown()` | `tools/cloud_shared/verify/verify_all_teardown_common.py` |
| Refactored AWS/GCP `verify_all_teardown.py` to use common | `tools/aws/.../verify_all_teardown.py`, `tools/gcp/.../verify_all_teardown.py` |

### Phase 2: PhaseTracker to cloud_shared

| Change | Files |
|--------|-------|
| Moved `PhaseTracker` to `tools/cloud_shared/core/phases.py` | `tools/cloud_shared/core/phases.py` (new) |
| AWS/GCP phases.py now import PhaseTracker from cloud_shared | `tools/aws/scope_shared/core/phases.py`, `tools/gcp/scope_shared/core/phases.py` |

### Phase 3: Config schema documentation

| Change | Files |
|--------|-------|
| Added unified config schema doc | `docs/CONFIG_SCHEMA.md` |

### Phase 4: DB Setup DRY

GCP db_setup was already refactored per `docs/REFACTOR_DB_SETUP_DRY.md`:
- `db_common.py` uses `FORCE_DROP_TABLES` from `setup_database_utils`, `parse_sql_statements` from cloud_shared
- `load.py` provides shared `load_embeddings()`
- AWS continues to use RDS Data API path (host-based)

---

## Validation

- `orchestrator.py doctor --provider aws --env dev --cloud-region us-east-1` ✓
- `orchestrator.py doctor --provider gcp --env dev --cloud-region us-central1` ✓
- All verify/deploy/teardown imports succeed ✓

---

## Rollback

```bash
git checkout pre-consolidate-refactor-YYYYMMDD
# or
git revert <commit-range>
```
