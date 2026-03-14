# Refactor Plan: Wait-for-Capacity Checks (min_node_count, min_instance_count)

## Goal

Add explicit waits for compute capacity before scheduling workload, so pods/tasks distribute across available resources instead of piling on the first available node. Addresses resource exhaustion (War Story 40–41) and imbalanced placement when nodes come up sequentially.

**Scope:** kube (min_node_count) and nonkube (min_instance_count), across AWS and GCP.

---

## 1. Problem Summary

| Scenario | Current behavior | Desired behavior |
|----------|------------------|-------------------|
| **Kube from scratch** | tofu apply → nodes launch async → kube_apply immediately → pods schedule on first Ready node only | Wait for min_node_count Ready nodes → then kube_apply → pods spread |
| **Kube after node replacement** | Same: kube_apply may run with 1 node | Same: wait for min_node_count before helm/kube_apply |
| **Nonkube ECS** | tofu apply → ECS sets desired_count → run_ecs_bootstrap immediately | Wait for runningCount ≥ min_instance_count → then bootstrap |
| **Nonkube Cloud Run** | tofu apply → run_analytics_bootstrap | Wait for revision ready (or min instances) → then bootstrap |

---

## 2. Limits of Centralization

| Check | Provider-agnostic? | Reason |
|-------|--------------------|--------|
| **min_node_count (kube)** | Yes | Both EKS and GKE use kubectl; `kubectl get nodes` works identically |
| **min_instance_count (ECS)** | No | AWS ECS API (`describe-services`, `runningCount`) |
| **min_instance_count (Cloud Run)** | No | GCP Cloud Run API; different semantics (revision vs instance count) |

**Constraint:** `tools/cloud_shared/` must NOT import `tools/aws/` or `tools/gcp/` to avoid circular dependencies. Therefore:

- **Kube waiter:** Lives in `tools/cloud_shared/deploy/` — fully shared
- **Nonkube waiters:** Live in provider modules — `tools/aws/...` and `tools/gcp/...`

---

## 3. Proposed File Structure

```
tools/
  cloud_shared/
    deploy/
      wait_for_capacity.py      # wait_for_kube_nodes_ready(min_count, ...)
  aws/
    scope_shared/
      deploy/
        wait_for_ecs.py         # wait_for_ecs_service_ready(cluster, service, min_count, region, ...)
  gcp/
    scope_shared/
      deploy/
        wait_for_cloud_run.py   # wait_for_cloud_run_revision_ready(service, region, project, ...)
```

**Alternative:** Put `wait_for_ecs.py` in `tools/aws/nonkube/` if we prefer nonkube-specific placement. Putting it in `scope_shared/deploy` keeps deploy helpers together.

---

## 4. Kube: wait_for_kube_nodes_ready

### 4.1 Signature

```python
def wait_for_kube_nodes_ready(
    min_count: int,
    timeout_seconds: int = 600,
    interval_seconds: int = 15,
    region: str | None = None,
) -> None:
    """
    Poll kubectl get nodes until at least min_count nodes are Ready.
    Works for EKS and GKE. Assumes kubeconfig targets the correct cluster.
    Raises TimeoutError if not reached within timeout_seconds.
    """
```

### 4.2 Implementation sketch

- Run `kubectl get nodes -o json` (or `jsonpath`)
- Count nodes with `status.conditions[?(@.type=="Ready")].status=="True"`
- Loop: if count >= min_count, return; else sleep(interval), retry
- On timeout: raise TimeoutError with message including current node count

### 4.3 Config source

Caller passes `min_count` from `get_kube_compute_config(region)["min_node_count"]`. No config loading inside the waiter.

### 4.4 Call sites

| File | When | Skip when |
|------|------|-----------|
| `tools/aws/kube/deploy_kube.py` | After `_apply_eks`, before `_install_nlb` (Phase 9.5) | `plan_clean` (no apply) |
| `tools/gcp/kube/deploy_kube.py` | After GKE apply, before kube_apply | Plan showed no changes |
| `tools/gcp/kube/reapply_kube_with_lb.py` | After apply, before kube_apply (if apply changed node pool) | Optional: only if apply ran |

### 4.5 Env vars (optional)

- `KUBE_NODE_WAIT_TIMEOUT_SEC` (default 600)
- `KUBE_NODE_WAIT_INTERVAL_SEC` (default 15)

---

## 5. Nonkube AWS: wait_for_ecs_service_ready

### 5.1 Signature

```python
def wait_for_ecs_service_ready(
    cluster_name: str,
    service_name: str,
    min_count: int,
    region: str,
    timeout_seconds: int = 300,
    interval_seconds: int = 10,
) -> None:
    """
    Poll ECS describe-services until runningCount >= min_count.
    Raises TimeoutError if not reached.
    """
```

### 5.2 Implementation sketch

- `aws ecs describe-services --cluster X --services Y --region Z`
- Parse `services[0].runningCount`
- Loop until runningCount >= min_count

### 5.3 Resource names

- `cluster_name`: `resource_names.ecs_cluster(env, region)`
- `service_name`: `f"{resource_names.get_proj_prefix()}-{env}-api-svc"` (from deploy_common.py)

### 5.4 Call site

| File | When | Skip when |
|------|------|-----------|
| `tools/aws/nonkube/deploy_nonkube.py` | After `apply_stack_nonkube_with_ecs_import_retry`, before frontend deploy / ECS bootstrap | `plan_clean` |

### 5.5 Env vars (optional)

- `ECS_SERVICE_WAIT_TIMEOUT_SEC` (default 300)
- `ECS_SERVICE_WAIT_INTERVAL_SEC` (default 10)

---

## 6. Nonkube GCP: wait_for_cloud_run_revision_ready

### 6.1 Semantics

Cloud Run differs from ECS:

- **Scale-to-zero:** min_instance_count may be 0
- **"Ready"** = revision deployed and serving traffic, not necessarily N instances
- Instance count is not as directly observable as ECS runningCount

### 6.2 Options

| Option | What we wait for | Pros | Cons |
|--------|------------------|------|------|
| A | Revision status = Ready | Simple; gcloud run services describe | Doesn't guarantee min instances |
| B | First successful HTTP request to API URL | Strong signal | Requires URL, network |
| C | Skip explicit wait; rely on run_analytics_bootstrap | No new code | Bootstrap may run before service ready |

**Recommendation:** Option A for now. Wait for the latest revision to be Ready. If min_instance_count > 0, Cloud Run keeps instances warm; revision Ready implies service can accept traffic.

### 6.3 Signature

```python
def wait_for_cloud_run_revision_ready(
    service_name: str,
    region: str,
    project_id: str,
    timeout_seconds: int = 300,
    interval_seconds: int = 10,
) -> None:
    """
    Poll Cloud Run service until latest revision is Ready.
    Uses gcloud run services describe or Cloud Run API.
    """
```

### 6.4 Call site

| File | When | Skip when |
|------|------|-----------|
| `tools/gcp/nonkube/deploy_nonkube.py` | After `run_deploy_stack`, before `run_analytics_bootstrap` | `not args.apply` or plan showed no changes |

### 6.5 Env vars (optional)

- `CLOUD_RUN_WAIT_TIMEOUT_SEC` (default 300)

---

## 7. Implementation Order

| Phase | Task | Files |
|-------|------|-------|
| 1 | Create `wait_for_capacity.py` with `wait_for_kube_nodes_ready` | `tools/cloud_shared/deploy/wait_for_capacity.py` |
| 2 | Integrate into AWS deploy_kube | `tools/aws/kube/deploy_kube.py` |
| 3 | Integrate into GCP deploy_kube | `tools/gcp/kube/deploy_kube.py` |
| 4 | Integrate into GCP reapply_kube_with_lb (if applicable) | `tools/gcp/kube/reapply_kube_with_lb.py` |
| 5 | Create `wait_for_ecs.py` with `wait_for_ecs_service_ready` | `tools/aws/scope_shared/deploy/wait_for_ecs.py` |
| 6 | Integrate into AWS deploy_nonkube | `tools/aws/nonkube/deploy_nonkube.py` |
| 7 | Create `wait_for_cloud_run.py` with `wait_for_cloud_run_revision_ready` | `tools/gcp/scope_shared/deploy/wait_for_cloud_run.py` |
| 8 | Integrate into GCP deploy_nonkube | `tools/gcp/nonkube/deploy_nonkube.py` |
| 9 | Add env var support (optional) | All wait modules |
| 10 | Update RESOURCE_ALLOCATION_CONFIG_YAML.md §7 | `docs/learned/cloud_shared/RESOURCE_ALLOCATION_CONFIG_YAML.md` |

---

## 8. Skip Logic

| Condition | Action |
|-----------|--------|
| **Kube:** `plan_clean` (tofu apply skipped) | Skip wait — nodes already exist from previous apply |
| **Kube:** First deploy (no cluster yet) | Always wait — apply creates nodes |
| **Nonkube ECS:** `plan_clean` | Skip wait — service already at desired count |
| **Nonkube Cloud Run:** `not args.apply` | Skip wait — no apply ran |

---

## 9. Error Handling

- **Timeout:** Raise `TimeoutError` with clear message: "Expected N Ready nodes; got M after Xs"
- **kubectl/aws/gcloud not found:** Let subprocess raise; or catch and re-raise with hint
- **Cluster not configured:** kubectl may fail with "connection refused" — same as today; no special handling

---

## 10. Testing

- **Unit:** Mock subprocess/check_output; assert correct retry logic
- **Integration:** Manual test: create cluster from scratch, verify wait runs and pods distribute
- **Skip path:** Run deploy with no changes; verify wait is skipped (log message)

---

## 11. References

- [RESOURCE_ALLOCATION_CONFIG_YAML.md](learned/cloud_shared/RESOURCE_ALLOCATION_CONFIG_YAML.md) — Config structure, min_node_count rationale
- [EKS_NODE_KUBELET_CRONJOB.md](learned/cloud_shared/EKS_NODE_KUBELET_CRONJOB.md) — Recovery, diagnostics
- [WAR_STORIES_CLOUD_SHARED.md](war_stories/WAR_STORIES_CLOUD_SHARED.md) §40–41 — CronJob overload, node replacement
