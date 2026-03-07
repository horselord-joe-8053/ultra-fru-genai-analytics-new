# Kubernetes Load Balancer Choice: NLB vs Classic ELB

LB choice content from KUBE_INGRESS_LEARNED. Our kube API is exposed via `fru-api-svc` (type LoadBalancer), **not** NGINX Ingress.

---

## 1. The Two Tracks

| Track | Flag | Manifest | Who creates LB | LB type |
|-------|------|----------|----------------|---------|
| **NLB** (default) | *no* `--elb` | `api-service.yaml` | AWS Load Balancer Controller | Network Load Balancer |
| **Classic ELB** | `--elb` | `api-service-elb.yaml` | In-tree cloud provider | Classic ELB (legacy) |

### What NLB and Classic ELB Are

- **Classic ELB** — AWS's original load balancer (pre-2016). Layer 4/7. Creates `k8s-elb-{hex}` security groups. DNS: `*.elb.amazonaws.com`.
- **NLB (Network Load Balancer)** — Newer (2017+). Layer 4 only, lower latency, higher throughput, static IPs. Preferred for API traffic.

### In-Tree vs Out-of-Tree

| Reconciler | Where | What it creates |
|------------|-------|-----------------|
| **In-tree cloud provider** | Inside Kubernetes (`kube-controller-manager`) | Classic ELB + `k8s-elb-*` SGs |
| **AWS Load Balancer Controller** (out-of-tree) | Separate controller (Helm) | NLB, ALB |

**Critical wiring:** `service.beta.kubernetes.io/aws-load-balancer-type: external` → AWS Load Balancer Controller reconciles → NLB. **Absent** → in-tree reconciles → Classic ELB.

---

## 2. Annotations

**`api-service.yaml` (NLB):**
```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
  service.beta.kubernetes.io/aws-load-balancer-type: external
  service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: instance
```

**`api-service-elb.yaml` (Classic ELB):**
```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
# No aws-load-balancer-type → in-tree creates Classic ELB
```

---

## 3. Deploy Flow

```
orchestrator.py deploy --provider aws --scope kube [--elb] [--cloud-region REGION]
    └── Phase 9.5: Install AWS Load Balancer Controller  (skipped when --elb)
    └── kube_apply.py [--elb]
            └── api_svc_manifest = "api-service-elb.yaml" if args.elb else "api-service.yaml"
```

- **With `--elb`:** Classic ELB. No controller install.
- **Without `--elb`:** NLB. Phase 9.5 installs controller before kube_apply.

---

## 4. Subnet Tags (LB Placement)

`kubernetes.io/role/elb` and `kubernetes.io/cluster/<cluster_name>` enable LB placement in **public** subnets. Without them → NLB in private subnets → CloudFront 502.

---

## 5. When to Use Each

| Use case | Track |
|----------|-------|
| **Default, recommended** | NLB (no `--elb`) |
| **Fallback / pre-migration** | Classic ELB (`--elb`) — no eksctl/helm |
| **Orphan cleanup after migration** | After switching to NLB, run `remove_for_orphans_data.py` for old Classic ELBs + `k8s-elb-*` SGs |

---

## 6. VPC Teardown: Classic ELB Track

When using Classic ELB, teardown must remove the `k8s-elb-*` security group **after** kube destroy and **before** durable (VPC) destroy.

| Resource | Who creates | When deleted | Blocks |
|----------|-------------|--------------|--------|
| Classic ELB | In-tree | `kubectl delete svc fru-api-svc` | — |
| `k8s-elb-{hex}` SG | In-tree (with ELB) | **Not** auto-deleted when ELB gone | VPC delete |
| ENIs (from ELB) | AWS | Async release 10–30 min after ELB delete | SG delete until released |

**Teardown order:** Pre kube (kubectl delete svc) → destroy kube → `remove_orphaned_k8s_elb_security_groups` → destroy durable.

---

## 7. Key Files

| File | Purpose |
|------|---------|
| `infra_terraform/modules/cloud_shared/k8s/api-service.yaml` | NLB manifest (default) |
| `infra_terraform/modules/cloud_shared/k8s/api-service-elb.yaml` | Classic ELB manifest (`--elb`) |
| `tools/aws/kube/kube_apply.py` | Selects manifest, applies via kubectl |
| `tools/aws/kube/kube_pre_destroy.py` | Teardown: kubectl delete |
| `tools/aws/kube/teardown_orphan_cleanup.py` | `remove_orphaned_k8s_elb_security_groups` |
