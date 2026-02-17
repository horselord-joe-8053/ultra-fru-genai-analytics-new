# tools/aws/ Big Reorganization Refactor Plan

This document describes the reorganization of `tools/aws/` into a modular layout with clear separation of concerns. **Refactor completed** (see git history).

---

## 1. Target File Structure

```
tools/aws/
├── __init__.py
├── deploy.py                      # Orchestrator (stays at root)
├── teardown.py                    # Orchestrator (stays at root)
├── terra_var_handling.py          # .env → TF_VAR_* mapping (at root; not AWS-specific)
│
├── standalone/                    # Standalone scripts (doctor, destroy_durable)
│   ├── __init__.py
│   ├── doctor.py
│   └── destroy_durable.py
│
├── common/                        # Shared by kube and nonkube
│   ├── __init__.py
│   │
│   ├── core/                      # Backend, Terraform runner—foundational infra
│   │   ├── __init__.py
│   │   ├── backend.py             # S3 backend config, resolve_region, stack_id_from_dir
│   │   └── terra_runner.py       # terra(), get_terra_env(), ensure_shared_terra_env()
│   │
│   ├── deploy/                    # Shared deploy logic
│   │   ├── __init__.py
│   │   ├── deploy_common.py
│   │   ├── deploy_frontend.py
│   │   ├── bootstrap_helpers.py
│   │   ├── bootstrap_state_backend.py
│   │   ├── build_and_push_images.py
│   │   ├── ensure_secrets.py
│   │   └── setup_database.py
│   │
│   ├── verify/                    # Verification scripts
│   │   ├── __init__.py
│   │   ├── verify_all_deploy.py
│   │   ├── verify_all_teardown.py
│   │   └── verify_db_password.py
│   │
│   └── utils/
│       ├── init_terra_upgrade_reconfigure.sh
│       └── README.md
│
├── kube/                          # Kubernetes/EKS-specific
│   ├── __init__.py
│   ├── kube_apply.py
│   ├── eks_kubeconfig.py
│   ├── teardown_orphan_cleanup.py
│   └── deploy_kube.py
│
├── nonkube/                       # ECS/non-Kubernetes
│   ├── __init__.py
│   ├── deploy_nonkube.py
│   └── ecs_spark_schedule.py
│
└── temp-one-off/                  # One-off scripts (unchanged)
    ├── import_state.py
    ├── fix_kube_db_credentials.py
    ├── diagnose_api_db.py
    ├── migrate_state_to_region_key.py
    ├── reconcile_state.py
    └── README.md
```

---

## 2. File Movement Map

| Current Location | New Location |
|------------------|--------------|
| `backend.py` | `common/core/backend.py` |
| `tofu/tofu_runner.py` | `common/core/terra_runner.py` (tofu/ subdir removed) |
| `tofu/__init__.py` | **Deleted** (no longer needed) |
| `doctor.py` | `standalone/doctor.py` |
| `destroy_durable.py` | `standalone/destroy_durable.py` |
| `deploy_common.py` | `common/deploy/deploy_common.py` |
| `deploy_frontend.py` | `common/deploy/deploy_frontend.py` |
| `bootstrap_helpers.py` | `common/deploy/bootstrap_helpers.py` |
| `bootstrap_state_backend.py` | `common/deploy/bootstrap_state_backend.py` |
| `build_and_push_images.py` | `common/deploy/build_and_push_images.py` |
| `ensure_secrets.py` | `common/deploy/ensure_secrets.py` |
| `setup_database.py` | `common/deploy/setup_database.py` |
| `verify_all_deploy.py` | `common/verify/verify_all_deploy.py` |
| `verify_all_teardown.py` | `common/verify/verify_all_teardown.py` |
| `verify_db_password.py` | `common/verify/verify_db_password.py` |
| `utils/` | `common/utils/` |
| `kube_apply.py` | `kube/kube_apply.py` |
| `eks_kubeconfig.py` | `kube/eks_kubeconfig.py` |
| `teardown_orphan_cleanup.py` | `kube/teardown_orphan_cleanup.py` |
| `deploy_kube.py` | `kube/deploy_kube.py` |
| `deploy_nonkube.py` | `nonkube/deploy_nonkube.py` |
| `ecs_spark_schedule.py` | `nonkube/ecs_spark_schedule.py` |
| `deploy.py` | **Stays** at root |
| `teardown.py` | **Stays** at root |
| `terra_var_handling.py` | **Stays** at root |
| `temp-one-off/*` | **Stays** at root |

---

## 3. Renames Within Files

### 3.1 terra_runner.py (from tofu/tofu_runner.py)

| Current | New |
|---------|-----|
| `tofu(cmd, ...)` | `terra(cmd, ...)` |
| `get_tofu_env()` | `get_terra_env()` |
| `ensure_shared_tofu_env()` | `ensure_shared_terra_env()` |

Rationale: `FRU_TF_BIN` in `.env` can be `tofu` or `terraform`; the module name and function names should reflect the generic Terraform/OpenTofu concept, not OpenTofu specifically.

### 3.2 Docstrings and Comments

Update references from "tofu" to "Terraform/OpenTofu" where appropriate in `terra_runner.py`.

---

## 4. Import Path Changes

### 4.1 Core / Terraform

| Old Import | New Import |
|------------|------------|
| `from tools.aws.backend import ...` | `from tools.aws.common.core.backend import ...` |
| `from tools.aws.tofu import tofu, get_tofu_env, ensure_shared_tofu_env` | `from tools.aws.common.core.terra_runner import terra, get_terra_env, ensure_shared_terra_env` |

### 4.2 Deploy

| Old Import | New Import |
|------------|------------|
| `from tools.aws.deploy_common import ...` | `from tools.aws.common.deploy.deploy_common import ...` |
| `from tools.aws.deploy_frontend import ...` | `from tools.aws.common.deploy.deploy_frontend import ...` |
| `from tools.aws.bootstrap_helpers import ...` | `from tools.aws.common.deploy.bootstrap_helpers import ...` |

### 4.3 Verify

| Old Import | New Import |
|------------|------------|
| `from tools.aws.verify_all_deploy import ...` | N/A (script, not imported) |
| `from tools.aws.verify_all_teardown import ...` | N/A |
| `from tools.aws.verify_db_password import ...` | N/A |

### 4.4 Kube

| Old Import | New Import |
|------------|------------|
| `from tools.aws.kube_apply import ...` | N/A (script) |
| `from tools.aws.eks_kubeconfig import ...` | N/A |
| `from tools.aws.teardown_orphan_cleanup import ...` | `from tools.aws.kube.teardown_orphan_cleanup import ...` |
| `from tools.aws.deploy_kube import ...` | `from tools.aws.kube.deploy_kube import ...` |

### 4.5 Nonkube

| Old Import | New Import |
|------------|------------|
| `from tools.aws.deploy_nonkube import ...` | `from tools.aws.nonkube.deploy_nonkube import ...` |
| `from tools.aws.ecs_spark_schedule import ...` | `from tools.aws.nonkube.ecs_spark_schedule import ...` |

### 4.6 Root (unchanged)

| Import | Location |
|--------|----------|
| `from tools.aws.terra_var_handling import get_base_vars` | Unchanged |

---

## 5. Subprocess Path Changes

All `subprocess.run(["python", "tools/aws/..."], ...)` and similar invocations must be updated.

### 5.1 deploy.py

| Old Path | New Path |
|----------|----------|
| `tools/aws/doctor.py` | `tools/aws/standalone/doctor.py` |
| `tools/aws/bootstrap_state_backend.py` | `tools/aws/common/deploy/bootstrap_state_backend.py` |
| `tools/aws/ensure_secrets.py` | `tools/aws/common/deploy/ensure_secrets.py` |
| `tools/aws/setup_database.py` | `tools/aws/common/deploy/setup_database.py` |
| `tools/aws/build_and_push_images.py` | `tools/aws/common/deploy/build_and_push_images.py` |

### 5.2 deploy_kube.py (→ kube/deploy_kube.py)

| Old Path | New Path |
|----------|----------|
| `tools/aws/kube_apply.py` | `tools/aws/kube/kube_apply.py` |

### 5.3 bootstrap_helpers.py (→ common/deploy/bootstrap_helpers.py)

| Old Path | New Path |
|----------|----------|
| `tools/aws/eks_kubeconfig.py` | `tools/aws/kube/eks_kubeconfig.py` |

### 5.4 kube_apply.py (→ kube/kube_apply.py)

| Old Path | New Path |
|----------|----------|
| `tools/aws/eks_kubeconfig.py` | `tools/aws/kube/eks_kubeconfig.py` |

### 5.5 temp-one-off/fix_kube_db_credentials.py

| Old Path | New Path |
|----------|----------|
| `tools/aws/ensure_secrets.py` | `tools/aws/common/deploy/ensure_secrets.py` |
| `tools/aws/kube_apply.py` | `tools/aws/kube/kube_apply.py` |

### 5.6 orchestrator.py (repo root)

| Old Path | New Path |
|----------|----------|
| `tools/aws/doctor.py` | `tools/aws/standalone/doctor.py` |
| `tools/aws/verify_all_teardown.py` | `tools/aws/common/verify/verify_all_teardown.py` |
| `tools/aws/verify_all_deploy.py` | `tools/aws/common/verify/verify_all_deploy.py` |

---

## 6. Function Call Updates (tofu → terra)

All callers of `tofu()`, `get_tofu_env()`, `ensure_shared_tofu_env()` must be updated:

| Old | New |
|-----|-----|
| `tofu(["apply", ...])` | `terra(["apply", ...])` |
| `get_tofu_env(region)` | `get_terra_env(region)` |
| `ensure_shared_tofu_env()` | `ensure_shared_terra_env()` |

**Files to update:**
- `deploy_common.py` → `common/deploy/deploy_common.py`
- `teardown.py`
- `destroy_durable.py` → `standalone/destroy_durable.py`
- `ensure_secrets.py` → `common/deploy/ensure_secrets.py`
- `build_and_push_images.py` → `common/deploy/build_and_push_images.py`
- `setup_database.py` → `common/deploy/setup_database.py`
- `verify_db_password.py` → `common/verify/verify_db_password.py`
- `verify_all_deploy.py` → `common/verify/verify_all_deploy.py`
- `temp-one-off/import_state.py`

---

## 7. init_stack and tofu_output_json

- `init_stack()` and `tofu_output_json()` live in `deploy_common.py`.
- `verify_all_deploy.py` and `fix_kube_db_credentials.py` currently import `from tools.aws.deploy import init_stack`—`deploy.py` does not export this. They should import from `deploy_common` instead.
- **After refactor:** `from tools.aws.common.deploy.deploy_common import init_stack, tofu_output_json`

---

## 8. Backward Compatibility (Optional)

If external code or scripts import from `tools.aws`, consider adding re-exports in `tools/aws/__init__.py`:

```python
# tools/aws/__init__.py
from tools.aws.terra_var_handling import get_base_vars
from tools.aws.common.core.backend import resolve_region, backend_config, stack_id_from_dir
# ... etc.
```

This is optional; prefer updating callers to use the new paths.

---

## 9. Documentation Updates

Update all docs that reference `tools/aws/` paths:

| Document | Paths to Update |
|----------|-----------------|
| `README.md` | deploy, teardown, destroy_durable |
| `README_WAR_STORIES.md` | verify_db_password, ensure_secrets, kube_apply, fix_kube_db_credentials, deploy_frontend, bootstrap_helpers, terra_var_handling |
| `docs/learned/terra/TERRA_LEARNED_TOFU.md` | destroy_durable, ensure_secrets, terra_runner |
| `docs/learned/terra/TERRA_LEARNED_TOTAL.md` | backend |
| `docs/FINAL_REFACTOR_PLAN.md` | backend |
| `docs/FINAL_REFACTOR_PLAN_2.md` | backend, terra_var_handling |
| `docs/LEGACY_VS_NEW_COMPARISON.md` | setup_database, terra_var_handling |
| `docs/AWS_AURORA_CLOUDFRONT_PLACEMENT.md` | backend |
| `live-deploy-aws/shared/durable/README.md` | deploy |
| `tools/aws/utils/init_terra_upgrade_reconfigure.sh` | Comment referencing backend.py |

---

## 10. Execution Order

Recommended order for performing the refactor:

1. **Create directory structure** – `standalone/`, `common/`, `common/core/`, `common/deploy/`, `common/verify/`, `kube/`, `nonkube/` with `__init__.py` files.
2. **Rename tofu → terra** – In `tofu/tofu_runner.py`, rename functions; save as `common/core/terra_runner.py`; delete `tofu/`.
3. **Move core** – Move `backend.py` → `common/core/backend.py`.
4. **Move deploy** – Move deploy-related files to `common/deploy/`.
5. **Move verify** – Move verify scripts to `common/verify/`.
6. **Move utils** – Move `utils/` → `common/utils/`.
7. **Move standalone** – Move `doctor.py`, `destroy_durable.py` → `standalone/`.
8. **Move kube** – Move kube files to `kube/`.
9. **Move nonkube** – Move nonkube files to `nonkube/`.
10. **Update imports** – Update all `from tools.aws.X` across the codebase.
11. **Update subprocess paths** – Update all `["python", "tools/aws/..."]` invocations.
12. **Update function calls** – Replace `tofu`/`get_tofu_env`/`ensure_shared_tofu_env` with `terra`/`get_terra_env`/`ensure_shared_terra_env`.
13. **Update orchestrator.py** – Update script paths.
14. **Update docs** – Update README and docs/*.
15. **Verify** – Run `python tools/aws/deploy.py --scope nonkube --env dev` (or kube) and `python tools/aws/teardown.py --scope nonkube --env dev --non-interactive` to confirm behavior.

---

## 11. Entry Points (Unchanged)

These remain valid after the refactor:

```bash
python tools/aws/deploy.py --scope kube --env dev
python tools/aws/deploy.py --scope nonkube --env dev
python tools/aws/deploy.py --scope all --env dev
python tools/aws/teardown.py --scope kube --env dev --non-interactive
python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
python tools/aws/teardown.py --scope all --env dev --non-interactive
```

Orchestrator usage also unchanged:

```bash
python orchestrator.py deploy --scope kube --env dev
python orchestrator.py teardown --scope nonkube --env dev
python orchestrator.py doctor --env dev
python orchestrator.py verify --scope kube --env dev
```

---

## 12. Design Rationale

| Decision | Rationale |
|----------|-----------|
| `deploy.py`, `teardown.py` at root | Main entry points; keep `python tools/aws/deploy.py` working |
| `terra_var_handling.py` at root | Shared by all; not AWS-specific; Terraform variable handling |
| `standalone/` for doctor, destroy_durable | Standalone scripts, not part of deploy/teardown flow |
| `common/core/` | Backend config and Terraform runner—foundational infra |
| `common/deploy/` | Shared deploy logic (tofu apply, bootstrap, build, secrets, DB) |
| `common/verify/` | Post-deploy and post-teardown verification |
| `tofu/` → `terra_runner.py` | Single file; no subdir; name reflects Terraform/OpenTofu |
| `temp-one-off/` at root | One-off scripts; separate from main flow |
