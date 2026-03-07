# Backend Scaling for Kubernetes Stacks (Multi-Cloud)

How kube (EKS/GKE) scaling works, how it differs from nonkube (Cloud Run/App Runner), and future paths to elasticity.

**Related:** [BACKEND_SCALING_NONKUBE_MULTI_CLOUD.md](./BACKEND_SCALING_NONKUBE_MULTI_CLOUD.md) — nonkube scaling and cold starts.

---

## Table of Contents

1. [Nodes vs Pods](#1-nodes-vs-pods)
2. [Current Setup: Fixed Capacity](#2-current-setup-fixed-capacity)
3. [Load Balancer Role](#3-load-balancer-role)
4. [EKS Node Sizing: Final Choice](#4-eks-node-sizing-final-choice)
5. [Future: Config-Based Node Sizing](#5-future-config-based-node-sizing)
6. [Future: Elasticity (HPA + Cluster Autoscaler)](#6-future-elasticity-hpa--cluster-autoscaler)
7. [Quick Reference](#7-quick-reference)

---

## 1. Nodes vs Pods

| Concept | Meaning | Controlled By |
|---------|---------|---------------|
| **Node** | Worker machine (EC2 on EKS, VM on GKE). Has CPU/memory capacity. | `desired_nodes` (EKS node group), Terraform |
| **Pod** | Container(s) running on a node. API pods, Spark jobs, etc. | Deployment `replicas`, k8s manifests |
| **Pods per node** | Many. Depends on node size and pod resource requests. | Implicit (scheduler) |

**Important:** `desired_nodes=3` means **3 worker nodes**, not 3 pods. Pod count is set separately in the Deployment YAML (e.g. `replicas: 2`).

---

## 2. Current Setup: Fixed Capacity

| Component | AWS (EKS) | GCP (GKE) | Elastic? |
|-----------|-----------|-----------|----------|
| Node group size | `desired_nodes` (Terraform default: 1) | Node pool config | No |
| Pod replicas | `replicas: 2` in Deployment | Same | No |
| Load balancer | NLB (AWS Load Balancer Controller) | L4/L7 LB | Routes only |

The load balancer **distributes traffic across existing pods**. It does **not** start new pods or nodes. Current kube setup is **fixed-capacity**—no request-driven auto-scaling.

---

## 3. Load Balancer Role

Both AWS and GCP kube stacks put an NLB (or equivalent) in front of the API pods:

- **AWS:** NLB via AWS Load Balancer Controller; CloudFront uses LB as API origin.
- **GCP:** Similar LB in front of GKE Service.

The LB routes requests to healthy pods. It does **not** trigger scale-up. To approximate Cloud Run/App Runner–style elasticity, you need **HPA** (pod scaling) and **Cluster Autoscaler** (node scaling).

---

## 4. EKS Node Sizing: Final Choice

**Problem:** `EKS_NODE_INSTANCE_TYPES` and `EKS_DESIRED_NODES` were required env vars but undocumented, not in `.env` or `.env.example`, causing deploy failures.

**Choice:** Remove the env-var wiring. Rely on Terraform defaults:

- `eks_instance_types`: `["t3.small"]` (from `infra_terraform/live_deploy/aws/kube/variables.tf`)
- `eks_desired_nodes`: `1`

**Impact:** Deploys work without hidden env vars. Node sizing is fixed at 1× t3.small until overridden via Terraform or future config wiring.

---

## 5. Future: Config-Based Node Sizing

**Why config, not .env:** Instance types vary by region (e.g. some types unavailable in us-east-2). Config is region-specific; `.env` is not.

**Intended design:** `config/cloud/aws_deploy_config.yaml` already has a `compute` section:

```yaml
default:
  compute:
    desired_nodes: 1
    node_instance_type: t3.small

us-east-2:
  compute:
    desired_nodes: 1
    node_instance_type: t3.small  # Override if region has different options
```

**Wiring:** `tools/aws/provider_config_handler.get_compute_config(region)` exists but is **not yet used** by `deploy_kube.py`. Future change:

1. Read `node_instance_type` and `desired_nodes` from `get_compute_config(region)`.
2. Pass them as `-var=eks_instance_types=[\"<type>\"]` and `-var=eks_desired_nodes=<n>` to Terraform.

**Reasonable values by environment:**

| Env | desired_nodes | node_instance_type |
|-----|---------------|---------------------|
| Dev | 1 | t3.small |
| Staging | 2 | t3.medium |
| Prod | 2–3 | m6i.large or r6i.large |

---

## 6. Future: Elasticity (HPA + Cluster Autoscaler)

To approach nonkube-style elasticity:

1. **Horizontal Pod Autoscaler (HPA):** Scale Deployment replicas up/down based on CPU, memory, or custom metrics (e.g. requests/sec).
2. **Cluster Autoscaler:** Add/remove nodes when pods cannot be scheduled (scale up) or nodes are underutilized (scale down).

**Notes:**

- Each node runs **many pods** (not one pod per node). Capacity depends on node size and pod requests.
- Cluster Autoscaler can scale the node group down toward 0 if min is set to 0 (EKS/GKE support varies).
- HPA + Cluster Autoscaler together give pod-level and node-level elasticity.

---

## 7. Quick Reference

| Question | Answer |
|----------|--------|
| Where is node count set? | Terraform `eks_desired_nodes` (default: 1). No env override. |
| Where is pod count set? | Deployment `replicas` in k8s manifests (e.g. `api-deployment-gcp.yaml`). |
| Does LB trigger scale-up? | No. LB routes to existing pods only. |
| Config for future node sizing? | `config/cloud/aws_deploy_config.yaml` → `compute.desired_nodes`, `compute.node_instance_type`. |
| How to add elasticity? | HPA (pods) + Cluster Autoscaler (nodes). |
