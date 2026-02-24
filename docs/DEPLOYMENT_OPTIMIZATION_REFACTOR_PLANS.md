# Deployment Run Optimization: Refactor Plans

Concise refactor plans for the identified deployment optimizations.

### Estimated Time Savings for Re-Deploy (when state is clean)

| Optimization | Typical savings | When it applies |
|--------------|-----------------|-----------------|
| **2.1** VPC tag lifecycle | ~30–60 s | Avoids durable apply touching subnets (tag drift); kube no longer re-adds tags. |
| **2.2** Single kube apply | ~1–5 min | Re-deploy: hostname known before first apply → skip second apply. |
| **2.3** Skip import + apply | ~2–8 min per stack | Plan shows no changes → skip import and Terraform apply for that stack. |
| **2.4** Content-based build skip | ~3–10 min | Hash matches → skip Docker build and push. |

**Rough total for a clean full-scope re-deploy:** ~5–20 minutes saved (nonkube + kube both clean, hostname known, build skipped).

### Actual Savings (2026-02-23 full-scope re-deploy, us-east-2, --skip-build)

Baseline: nonkube import (161.9s) and apply (24.9s) ran; kube was optimized.

| Optimization | Estimated | Actual (this run) | How derived |
|--------------|-----------|------------------|-------------|
| **2.1** VPC tag lifecycle | ~30–60 s | Not directly measurable | Preventive; durable showed "No changes." Before 2.1, tag drift would add churn on durable + kube. |
| **2.2** Single kube apply | ~1–5 min | ~1 min | Second kube apply skipped (kube tofu apply: 0.0s). Nonkube apply was 24.9s; kube apply similar. |
| **2.3** Skip import + apply | ~2–8 min/stack | ~2.5 min (kube) | Kube import + apply skipped. Nonkube import 161.9s; kube import ~60–90s. Kube apply ~25–60s. Saved ~2–3 min. |
| **2.4** Content-based build skip | ~3–10 min | ~4.5 min | Run 1 (build): 594s. Run 2 (hash match skip): 327s. Phase 7: 106s → 11s. |

**Total actual (2026-02-23 runs):** ~8–14 min saved (2.2 + 2.3 + 2.4). 2.1 is preventive. *Note: 2.4 was tested without `--skip-build`; first run built (no stored hash); second run skipped via content hash match.*

---

## 2.1 Durable vs Kube Subnet Tags — Clarification and Refactor Plan

### Why Kube Adds These Tags (Purpose)

The kube stack adds two subnet tags used when provisioning load balancers for Kubernetes Services (`type: LoadBalancer`):

| Tag | Value | Purpose |
|-----|-------|---------|
| `kubernetes.io/role/elb` | `1` | Marks the subnet as **eligible for internet-facing load balancers**. Without it, the controller places the NLB in private subnets by default → internal NLB → CloudFront (on the internet) cannot reach it → 502. |
| `kubernetes.io/cluster/<cluster_name>` | `shared` | Identifies subnets that belong to this EKS cluster. The controller uses this to know which subnets it can use for the cluster's load balancers. |

Our `fru-api-svc` Service has `service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing`. **Current:** In-tree creates Classic ELB. **With `aws-load-balancer-type: external`:** AWS Load Balancer Controller creates NLB. Subnet tags enable placement in public subnets. See War Story 43 and [KUBE_LOAD_BALANCER_CLARIFICATION.md](KUBE_LOAD_BALANCER_CLARIFICATION.md).

### What's Actually Happening

**Durable creates subnets** via `module.vpc`. The VPC module sets only `tags = merge(var.tags, { Name = ... })`—no k8s tags:

```hcl
# infra_terraform/modules/aws/primitives/vpc/main.tf
resource "aws_subnet" "public_protected" {
  count                   = local.protected * length(var.public_subnet_cidrs)
  ...
  tags = merge(var.tags, { Name = "${var.name}-public-${count.index}" })
}
```

**Kube adds k8s tags** to the same subnets (from durable outputs) using `aws_ec2_tag`:

```hcl
# infra_terraform/live_deploy/aws/kube/main.tf
# Tag public subnets so AWS Load Balancer Controller can place internet-facing NLBs there.
resource "aws_ec2_tag" "public_subnet_elb" {
  for_each    = toset(data.terraform_remote_state.shared_durable.outputs.public_subnet_ids)
  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}
resource "aws_ec2_tag" "public_subnet_cluster" {
  for_each    = toset(data.terraform_remote_state.shared_durable.outputs.public_subnet_ids)
  resource_id = each.value
  key         = "kubernetes.io/cluster/${module.eks.cluster_name}"
  value       = "shared"
}
```

**The drift cycle:**

1. Durable's `aws_subnet` has desired state `tags = X` (no k8s tags).
2. Kube adds k8s tags via `aws_ec2_tag` → actual subnet has `X + Y`.
3. On durable's next `plan`/`apply`, Terraform sees the subnet has extra tags (`Y`).
4. Durable's desired state is only `X`, so Terraform plans to remove `Y` to match.
5. Durable apply removes the k8s tags.
6. Kube's next apply adds them back via `aws_ec2_tag`.
7. Repeat.

So durable "removes" them only in the sense that Terraform enforces durable's desired state, which does not include the k8s tags that kube added.

### Refactor Plan

**Option A (recommended): `lifecycle { ignore_changes = [tags] }` on durable subnets**

- In `infra_terraform/modules/aws/primitives/vpc/main.tf`, add to `aws_subnet.public_*` and `aws_subnet.private_*`:

  ```hcl
  lifecycle {
    ignore_changes = [tags]
  }
  ```

- Durable sets initial tags on create; subsequent applies do not touch tags.
- Kube's `aws_ec2_tag` can add k8s tags without durable removing them.
- Trade-off: durable cannot change its own tags later; acceptable if tags are stable.

**Option B: Move k8s tags into durable**

- Add optional `eks_cluster_name` (or similar) to durable; when set, durable adds the k8s tags.
- Requires durable to depend on EKS cluster name, which may not be known at durable apply time.
- More invasive; not recommended unless you restructure apply order.

**Implementation:** Done. Option A applied in `infra_terraform/modules/aws/primitives/vpc/main.tf`. War Story 58.

---

## 2.2 Kube Apply Ran Twice — Clarification and Refactor Plan

### Why It Runs Twice

1. **First apply:** EKS stack without `ingress_hostname`. CloudFront's API origin is `null` or placeholder.
2. **In between:** `kube_apply` (bootstrap + schedule) runs; `fru-api-svc` LoadBalancer is applied; AWS (in-tree or AWS Load Balancer Controller) provisions the LB.
3. **Poll:** Deploy waits for `kubectl get svc fru-api-svc ... hostname` to be non-empty (up to ~3 min).
4. **Second apply:** Same kube stack with `ingress_hostname=<lb_host>` so CloudFront's API origin is set to the LB DNS.

The LB hostname is not known until Kubernetes creates the Service and AWS provisions the LB (currently Classic ELB; NLB with annotation). Terraform (kube stack) needs that hostname for the CloudFront module. Hence: first apply (no hostname) → k8s creates NLB → second apply (with hostname).

### Refactor Plan: Single Apply When Hostname Is Known

**Idea:** On re-deploys, the LB hostname is usually stable. If we can get it before the first apply, we can pass it in and skip the second apply.

**Steps:**

1. **Before first kube apply:** Try to get the LB hostname:
   - `kubectl get svc fru-api-svc -n <ns> -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'`
   - Or from prior Terraform output if we add `ingress_hostname` as an output (and it was set in a previous run).

2. **If hostname is non-empty:** Pass `-var ingress_hostname=<hostname>` in the first (and only) apply. Skip the second apply.

3. **If hostname is empty (fresh deploy):** Keep current behavior: first apply, kube_apply, poll for hostname, second apply.

**Implementation sketch:**

```python
# In deploy_kube.py, before _apply_eks:
hostname_before_first_apply = _try_get_lb_hostname(env, region)  # kubectl or prior tofu output
ingress_var = ["-var", f"ingress_hostname={hostname_before_first_apply}"] if hostname_before_first_apply else []

# First apply (with hostname if we already have it from prior deploy)
apply_stack(..., extra_vars=ingress_var)

# After kube_apply + wait for NLB:
hostname_after_poll = hostname_before_first_apply or _poll_lb_hostname(...)
need_second_apply = not hostname_before_first_apply and hostname_after_poll  # got it from poll, must update CloudFront
if need_second_apply:
    apply_stack(..., extra_vars=["-var", f"ingress_hostname={hostname_after_poll}"])
```

**Result:** Re-deploys often need one apply; fresh deploys still need two.

**Implementation:** Done. `tools/aws/kube/deploy_kube.py`: `_try_get_lb_hostname` before first apply; `need_second_apply` only when hostname from poll. War Story 59.

---

## 2.3 Import Pre-Existing — "Skip When State Is Clean"

### What "State Is Clean" Means

**Clean:** Terraform plan shows "No changes. Your infrastructure matches the configuration."
**Not clean:** Plan shows creates, updates, or destroys.

If plan shows no changes, we don't need to create anything, so we won't hit "already exists." Import is only useful when we might create resources that already exist in AWS. When plan is clean, import adds no value.

### Refactor Plan: Quick Plan Check Before Import

1. **Before import for a stack:** Run `tofu plan -detailed-exitcode` (or equivalent).
   - Exit 0: no changes → skip import and skip apply for that stack.
   - Exit 2: changes present → run import, then apply.
   - Exit 1: error → log and fail (or run import as today for safety).

2. **Caveat:** On first deploy, state may be empty; plan will show many creates. That's "not clean," so we still run import and apply. The optimization helps when state is already in sync.

3. **Scope:** Apply per stack (nonkube, kube). Shared stacks (durable, nondurable) may need the same pattern if they run import.

**Implementation sketch:**

```python
def should_skip_import(stack_dir, env, region) -> bool:
    """Return True if plan shows no changes (state clean)."""
    result = subprocess.run(
        [tofu_bin, "plan", "-detailed-exitcode"],
        cwd=stack_dir, env=get_terra_env(region), capture_output=True
    )
    # 0 = no changes, 2 = changes, 1 = error
    return result.returncode == 0

if should_skip_import(stack_dir, env, region):
    logger.info(f"[Import] Skipping {stack_dir}: plan shows no changes (state clean)")
    return  # skip import and optionally skip apply
# else: run import as today
```

**Result:** Saves import time when infrastructure is already in sync.

**Implementation:** Done. `tools/aws/scope_shared/deploy/deploy_common.py`: `plan_shows_no_changes()`. `deploy_kube.py` and `deploy_nonkube.py`: skip import and skip apply when plan shows no changes. War Story 60.

---

## 2.4 Build & Push — Content-Based Skip (Done)

### Status

Implemented. Content-based skip using build-context hash stored in S3. Skip when hash matches; `--force-build` bypasses. See **docs/BUILD_CONTENT_SKIP.md**. War Story 61.
