# Refactor Plan: config/cloud/*.yaml — Scope-Based, Bounded, Single Source of Truth

## Goal

Refactor `config/cloud/aws_deploy_config.yaml` and `config/cloud/gcp_deploy_config.yaml` to:

1. **Hierarchy:** `scope (scope_default | kube | nonkube) → region (regional_default | us-east-1 | ...)`
2. **Bounded everywhere:** `min_*` and `max_*` for all compute allocation (no desired/initial)
3. **Tasks structure:** `tasks.api` and `tasks.spark` with `cpu`/`memory` per task type
4. **DRY:** `regional_default` holds shared values; region blocks only override
5. **Fail-fast:** Missing required keys raise clear errors; no fallbacks elsewhere

---

## Target YAML Structure (Reference)

### AWS

```yaml
scope_default:
  regional_default:
    network:
      public_subnet_cidrs: ["10.0.1.0/24", "10.0.2.0/24"]
      private_subnet_cidrs: ["10.0.101.0/24", "10.0.102.0/24"]
    database:
      multi_az: false
  us-east-1:
    network:
      azs: [us-east-1a, us-east-1b]
  us-east-2:
    network:
      azs: [us-east-2a, us-east-2b]
  us-west-2:
    network:
      azs: [us-west-2a, us-west-2b]

kube:
  # min=2: Fix CronJob resource exhaustion. 1× t3.small (2GB) overloaded by Spark+fru-api+LB
  # → memory pressure → node unreachable. 2 nodes spread load. See EKS_NODE_KUBELET_CRONJOB.md
  regional_default:
    compute:
      min_node_count: 2
      max_node_count: 2
      node_instance_types: [t3.small]
  us-east-1:
    compute:
      min_node_count: 2
      max_node_count: 2
  us-east-2:
    compute:
      min_node_count: 2
      max_node_count: 2

nonkube:
  regional_default:
    compute:
      min_instance_count: 1
      max_instance_count: 2
      tasks:
        api:
          cpu: 512
          memory: 1024
        spark:
          cpu: 512
          memory: 1024
```

### GCP

```yaml
scope_default:
  regional_default:
    database:
      high_availability: false
  us-central1:
    network:
      zones: [us-central1-a]
  us-east1:
    network:
      zones: [us-east1-b]

kube:
  regional_default:
    compute:
      location_type: zonal
      min_node_count: 1
      max_node_count: 2
      machine_type: e2-small
  us-central1:
    compute:
      zone: us-central1-a
  us-east1:
    compute:
      zone: us-east1-b

nonkube:
  regional_default:
    compute:
      min_instance_count: 1
      max_instance_count: 2
      tasks:
        api:
          cpu: "1"
          memory: "512Mi"
        spark:
          cpu: "2"
          memory: "4Gi"
```

---

## Wiring Verification

| Consumer | Source | Keys Used | Verified |
|----------|--------|-----------|----------|
| deploy.py (durable) | scope_default | network.azs, network.public_subnet_cidrs, network.private_subnet_cidrs, database.multi_az | ✓ |
| teardown.py | scope_default | network.azs, network.*_subnet_cidrs | ✓ |
| destroy_durable.py | scope_default | network.azs, network.*_subnet_cidrs | ✓ |
| AWS deploy_kube | kube | compute.min_node_count, max_node_count, node_instance_types | ✓ |
| AWS deploy_nonkube | nonkube | compute.min_instance_count, max_instance_count, tasks.api, tasks.spark | ✓ |
| GCP deploy_kube | kube | compute.location_type, zone, min_node_count, max_node_count, machine_type | ✓ |
| GCP deploy_nonkube | nonkube | compute.min_instance_count, max_instance_count, tasks.api, tasks.spark | ✓ |
| GCP teardown | kube | compute (for initial_node_count → becomes min_node_count) | ✓ |
| GCP reapply_kube_with_lb | kube | compute | ✓ |

**Instance vs task (no contradiction):**

- `min/max_instance_count` = replica count (how many API containers)
- `tasks.api` = resources per API container
- Example: `min_instance_count: 2`, `tasks.api.cpu: 512` → 2 API tasks, each 512 CPU; load balancer distributes traffic, each gets ~half

---

## Implementation Order

**Note:** Phase 1 and 2 must be done together — the new loader expects the new YAML structure; deploy will break until both are complete.

### Phase 1: Config Loader and Handlers

| # | Task | File(s) |
|---|------|---------|
| 1.1 | Add `load_scope_config(provider, scope, region)` that merges `scope.regional_default` with `scope[region]` | `provider_config_utils.py` |
| 1.2 | Region validation: region must exist in `scope_default`; else `ValueError` | `provider_config_utils.py` |
| 1.3 | Add `_require(cfg, path, key)` for fail-fast; no defaults for config-sourced values | `provider_config_utils.py` or handlers |
| 1.4 | AWS handler: `get_network_config`, `get_database_config` from scope_default; `get_kube_compute_config`, `get_nonkube_compute_config` from kube/nonkube; all fail-fast | `tools/aws/provider_config_handler.py` |
| 1.5 | GCP handler: same pattern; `get_gke_location` from kube.compute.zone/region; `get_kube_compute_config`, `get_nonkube_compute_config` | `tools/gcp/provider_config_handler.py` |
| 1.6 | Deprecate or remove `get_compute_config` (no callers in deploy scripts) | both handlers |

### Phase 2: YAML Files

| # | Task | File(s) |
|---|------|---------|
| 2.1 | Restructure `aws_deploy_config.yaml` to scope_default, kube, nonkube | `config/cloud/aws_deploy_config.yaml` |
| 2.2 | Restructure `gcp_deploy_config.yaml` | `config/cloud/gcp_deploy_config.yaml` |

### Phase 3: AWS Kube (EKS)

| # | Task | File(s) |
|---|------|---------|
| 3.1 | EKS module: replace `desired_size` with `min_size`, `max_size`; `scaling_config { min_size, max_size, desired_size = min_size }` | `modules/aws/eks/main.tf`, `variables.tf` |
| 3.2 | Live kube: replace `eks_desired_nodes` with `eks_min_node_count`, `eks_max_node_count` | `live_deploy/aws/kube/variables.tf`, `main.tf` |
| 3.3 | Deploy: read from `get_kube_compute_config(region)`; set `TF_VAR_eks_min_node_count`, `TF_VAR_eks_max_node_count`, `TF_VAR_eks_instance_types` | `terra_var_handling.py` or `deploy_kube.py` |

### Phase 4: AWS Nonkube (ECS)

| # | Task | File(s) |
|---|------|---------|
| 4.1 | ECS module: replace `desired_count` with `min_instance_count`, `max_instance_count`; add `aws_appautoscaling_target` with `min_capacity`, `max_capacity`; `desired_count = min_instance_count` | `modules/aws/ecs/main.tf`, `variables.tf` |
| 4.2 | ECS module: add `api_task_cpu`, `api_task_memory`, `spark_task_cpu`, `spark_task_memory`; use in task definitions | `modules/aws/ecs/main.tf`, `variables.tf` |
| 4.3 | Live nonkube: replace `desired_count` with `min_instance_count`, `max_instance_count`; add task vars | `live_deploy/aws/nonkube/variables.tf`, `main.tf` |
| 4.4 | Deploy: read from `get_nonkube_compute_config(region)`; set TF_VARs for min/max and tasks | `terra_var_handling.py` or `deploy_nonkube.py` |

### Phase 5: GCP Kube (GKE)

| # | Task | File(s) |
|---|------|---------|
| 5.1 | GKE module: `remove_default_node_pool = true`, `initial_node_count = 1`; add `google_container_node_pool` with `autoscaling { min_node_count, max_node_count }`, `node_config { machine_type }` | `modules/gcp/gke/main.tf`, `variables.tf` |
| 5.2 | Live kube: replace `initial_node_count` with `min_node_count`, `max_node_count`; add `machine_type` | `live_deploy/gcp/kube/variables.tf`, `main.tf` |
| 5.3 | Deploy: read from `get_kube_compute_config(region)`; pass `-var=min_node_count`, `-var=max_node_count`, `-var=machine_type`, `-var=gke_location` | `tools/gcp/kube/deploy_kube.py` |
| 5.4 | **Migration:** Existing GKE clusters created with `initial_node_count` need manual migration or new cluster. Document in plan. | — |

### Phase 6: GCP Nonkube (Cloud Run)

| # | Task | File(s) |
|---|------|---------|
| 6.1 | Cloud Run module: add `resources { limits { cpu, memory } }` to containers when `cpu`/`memory` are set | `modules/gcp/cloud_run/main.tf` |
| 6.2 | Live nonkube: pass `cpu`, `memory` from vars to cloud_run module; pass `cpu`, `memory` to spark_job from vars | `live_deploy/gcp/nonkube/main.tf` |
| 6.3 | Live nonkube vars: add `api_task_cpu`, `api_task_memory`, `spark_task_cpu`, `spark_task_memory` (or derive from config) | `live_deploy/gcp/nonkube/variables.tf` |
| 6.4 | Deploy: read from `get_nonkube_compute_config(region)`; pass `-var=min_instance_count`, `-var=max_instance_count`, task vars | `tools/gcp/nonkube/deploy_nonkube.py` |

### Phase 7: Terraform Defaults Removal

| # | Task | File(s) |
|---|------|---------|
| 7.1 | Remove `default` for all config-driven vars; require them (fail if not passed) | `live_deploy/*/variables.tf`, `modules/*/variables.tf` |

### Phase 8: Docs and Callers

| # | Task | File(s) |
|---|------|---------|
| 8.1 | Update `CONFIG_SCHEMA.md` | `docs/CONFIG_SCHEMA.md` |
| 8.2 | Update `BACKEND_SCALING_*.md` | `docs/learned/cloud_shared/` |
| 8.3 | Update teardown, destroy_durable, reapply_kube_with_lb to use new handlers. GCP teardown: pass `min_node_count`, `max_node_count` instead of `initial_node_count` | `tools/aws/teardown.py`, `tools/aws/standalone/destroy_durable.py`, `tools/gcp/teardown.py`, `tools/gcp/kube/reapply_kube_with_lb.py` |

---

## Corrections and Edge Cases

### 1. Loader: Region in scope_default only

Region must exist in `scope_default` (for network). For `kube` and `nonkube`, if `scope[region]` is missing, merge with `scope.regional_default` only (no override). This keeps DRY: regions without overrides need no block.

### 2. GKE migration for existing clusters

Existing clusters use `initial_node_count` on the cluster. Switching to `remove_default_node_pool` + separate node pool requires:

- **New clusters:** Use new structure from the start.
- **Existing clusters:** Add node pool with autoscaling, then remove default pool, or recreate cluster. Document as migration path; consider feature-flag for gradual rollout.

### 3. ECS Application Auto Scaling

`aws_appautoscaling_target` requires `min_capacity`, `max_capacity`. With `min=max`, scaling is effectively fixed. No scaling policy needed for fixed count.

### 4. Cloud Run API resources

Cloud Run v2 `containers` block supports `resources { limits { cpu, memory } }`. Add when `var.cpu` and `var.memory` are non-null. Use format: `cpu = "1"`, `memory = "512Mi"`.

### 5. JSON for list vars (EKS)

`node_instance_types` is a list. Terraform `-var` expects JSON for lists: `-var='eks_instance_types=["t3.small"]'`.

### 6. AWS kube: min_node_count=2 (CronJob exhaustion fix)

1× t3.small (2GB) was overloaded by CronJob Spark + fru-api + LB controller → memory pressure → node unreachable. `min_node_count: 2` spreads load across 2 nodes. `max_node_count: 2` keeps it fixed (no autoscaler). See `docs/learned/cloud_shared/EKS_NODE_KUBELET_CRONJOB.md`.

---

## Summary Checklist

- [x] Phase 1: Loader + handlers
- [x] Phase 2: YAML files
- [x] Phase 3: AWS kube
- [x] Phase 4: AWS nonkube
- [x] Phase 5: GCP kube (callers updated; module migration deferred per §5.4)
- [ ] Phase 6: GCP nonkube (Cloud Run task resources - deferred)
- [ ] Phase 7: Remove Terraform defaults
- [x] Phase 8: Docs + callers (teardown, reapply, deploy_kube)

**Estimated effort:** 2–3 days. GKE migration adds risk for existing clusters.

---

## Final Confirmation: Setup Will Work

| Check | Status |
|-------|--------|
| Loader merge: `regional_default` + `scope[region]` produces correct merged config | ✓ |
| scope_default provides network + database for durable stack | ✓ |
| kube provides compute for EKS/GKE | ✓ |
| nonkube provides compute for ECS/Cloud Run | ✓ |
| tasks.api / tasks.spark map to ECS task defs and Cloud Run resources | ✓ |
| min/max_instance_count → ECS aws_appautoscaling_target + desired_count | ✓ |
| min/max_instance_count → Cloud Run scaling block (already supported) | ✓ |
| min/max_node_count → EKS scaling_config | ✓ |
| min/max_node_count → GKE node pool autoscaling | ✓ |
| Fail-fast: handlers raise on missing keys | ✓ |
