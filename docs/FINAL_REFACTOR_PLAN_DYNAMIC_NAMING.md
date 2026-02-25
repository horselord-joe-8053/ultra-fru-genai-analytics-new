# Final Refactor Plan: Dynamic Naming (PROJ_PREFIX + COMPONENT .env)

**Purpose:** Safely and smoothly accommodate dynamic name changes. This document is the single source of truth for the migration.

**Related:** `docs/FINAL_REFACTOR_RENAMING.md` — full .env renaming plan, naming convention, code impact, `resource_names.py` design.

---

## Part A: Migration Runbook (Step-by-Step)

**Critical:** The correct order is **teardown with current .env → resource scan & orphan removal → update .env → deploy with new .env → resource scan & orphan removal**. Reversing or skipping steps will leave orphaned resources or cause Terraform state mismatches.

### Step 1: Teardown with current .env (all regions, all scopes, incl-durable)

Run teardown for **each region** you have deployed to. Use the orchestrator with `--scope all`, `--incl-dura`, and `--non-interactive`.

```bash
# Region 1 (e.g. us-east-1)
.venv/bin/python orchestrator.py teardown --scope all --env dev --cloud-region us-east-1 --incl-dura --non-interactive

# Region 2 (e.g. us-east-2) — if you deploy to multiple regions
.venv/bin/python orchestrator.py teardown --scope all --env dev --cloud-region us-east-2 --incl-dura --non-interactive
```

**Notes:** Use `--cloud-region` per region (default from `CLOUD_REGION`). `--incl-dura` destroys shared durable (VPC, Aurora, Secrets). Ensure `.env` has **current** full-name vars (e.g. `S3_DELTA_BUCKET=fru-dev-delta-internal`, `EKS_CLUSTER_NAME=fru-dev-eks`).

---

### Step 2: Verify teardown (optional but recommended)

```bash
.venv/bin/python tools/aws/scope_shared/verify/verify_all_teardown.py --scope all --env dev --region us-east-1
.venv/bin/python tools/aws/scope_shared/verify/verify_all_teardown.py --scope all --env dev --region us-east-2
```

---

### Step 3: Resource scan and safely remove orphans

```bash
.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py \
  --cloud-regions us-east-1,us-east-2 --env dev --prefix fru

.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py --dry-run
# Review output; if safe:
.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py
```

**Note:** Add `--elb` to scan if using Classic ELB for kube (api-service-elb.yaml).

---

### Step 4: Update .env to PROJ_PREFIX and `*_COMPONENT` vars

**Before editing:** Back up `.env`.

**Refer to `docs/FINAL_REFACTOR_RENAMING.md`** for the full .env spec (Part C.1–C.2), naming convention (Part A, C.3), and frontend/scope handling.

**Summary:** Replace `FRU_PREFIX` with `PROJ_PREFIX`; replace full-name vars and combined prefixes with `*_COMPONENT` vars per RENAMING Part C.2. Remove or comment out the old vars.

| Change |
|--------|
| `FRU_PREFIX` → `PROJ_PREFIX` |
| `TF_STATE_*_PREFIX` → `TF_STATE_*_COMPONENT` |
| Full-name vars (`S3_DELTA_BUCKET`, `EKS_CLUSTER_NAME`, etc.) → `*_COMPONENT` |

---

### Step 5: Deploy with new .env (all scopes, all regions)

```bash
.venv/bin/python orchestrator.py deploy --scope all --env dev --cloud-region us-east-1
.venv/bin/python orchestrator.py deploy --scope all --env dev --cloud-region us-east-2 --skip-build
```

---

### Step 6: Post-deploy resource scan and orphan removal

```bash
.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py \
  --cloud-regions us-east-1,us-east-2 --env dev --prefix fru
.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py --dry-run
# Review output; if safe:
.venv/bin/python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py
```

---

## Part B: Other (Reference Only)

All details — .env inventory, `resource_names.py` design, terra_var_handling/backend changes, implementation phases, logging — are in `docs/FINAL_REFACTOR_RENAMING.md`. This plan defers to it to avoid inconsistency.
