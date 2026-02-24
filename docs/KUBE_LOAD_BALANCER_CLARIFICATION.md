# Kube Load Balancer: Actual vs Documented (Classic ELB vs NLB)

**Status:** Documentation correction. Many docs say "NLB"; the actual LB in use is **Classic ELB**.

---

## Current Reality (as of this clarification)

| What docs say | What actually happens |
|---------------|------------------------|
| NLB (Network Load Balancer) | **Classic ELB** (legacy) |
| AWS Load Balancer Controller creates it | **In-tree cloud provider** creates it |

### Why

The `fru-api-svc` Service (`api-service.yaml`) has:

```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
# Missing: service.beta.kubernetes.io/aws-load-balancer-type: external
```

**Without** `aws-load-balancer-type: external`, the **in-tree** (legacy) Kubernetes AWS cloud provider reconciles the Service. The in-tree creates **Classic ELBs** and `k8s-elb-*` security groups—not NLBs.

**With** `aws-load-balancer-type: external`, the **AWS Load Balancer Controller** (out-of-tree) would take over and create an **NLB** instead.

### Terminology

- **In-tree** = Code inside the main Kubernetes repo; creates Classic ELBs for LoadBalancer services.
- **Out-of-tree** = Separate controller (e.g. AWS Load Balancer Controller); creates NLBs/ALBs.

---

## Evidence

- Orphan scan finds **Classic ELBs** and **k8s-elb-{hex}** security groups—the in-tree’s signature.
- Deploy reads hostname from `fru-api-svc` and wires CloudFront to it; that hostname is the Classic ELB DNS.
- Both Classic and NLB use `*.elb.amazonaws.com` DNS, so the format alone doesn’t distinguish them.

---

## How to Switch to NLB

Add to `api-service.yaml`:

```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
  service.beta.kubernetes.io/aws-load-balancer-type: external
```

Then redeploy kube scope. The AWS Load Balancer Controller (if installed in the cluster) will create an NLB. CloudFront will be wired to the new NLB hostname. Old Classic ELB + `k8s-elb-*` pairs become orphans and can be removed via `remove_for_orphans_data.py`.

**Prerequisite:** AWS Load Balancer Controller is installed automatically during deploy (Phase 9.5) when using the NLB track (no `--elb`). See [REFACTOR_PLAN_NLB_DEPLOY_INTEGRATION.md](REFACTOR_PLAN_NLB_DEPLOY_INTEGRATION.md).

For the full picture (two tracks, `--elb` flag, manifest selection), see [learned/KUBE_INGRESS_LEARNED.md](learned/KUBE_INGRESS_LEARNED.md) Section 0 and War Story 64 in README_WAR_STORIES.md.

---

## Docs Updated by This Clarification

- `api-service.yaml` – comment
- `docs/learned/FULL_ARCH_KUBE_LEARN.md` – NLB → Classic ELB (current)
- `tools/aws/kube/deploy_kube.py` – comments
- `tools/aws/scope_shared/deploy/bootstrap_helpers.py` – comments
- `README_WAR_STORIES.md` – War Stories 4, 5, 55
- `infra_terraform/live_deploy/aws/kube/main.tf` – comment
- `infra_terraform/live_deploy/aws/kube/variables.tf` – comment
- `docs/DEPLOYMENT_OPTIMIZATION_REFACTOR_PLANS.md` – clarification
- `docs/learned/KUBE_INGRESS_LEARNED.md` – Section 0: Classic ELB vs NLB choice, `--elb` flag, manifest selection
- `docs/learned/VPC_LEARNED.md`, `docs/learned/terra/TERRA_STACK_OWNERSHIP_AND_SHARED_RESOURCES.md` – LB placement
- `docs/ANALYSIS_US_EAST_1_DEPLOY_ERRORS_AFTER_US_EAST_2_TEARDOWN.md` – clarification
