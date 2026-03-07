# VPC & Network Concepts

Concepts from VPC_LEARNED. For Terraform layers and state, see [TERRA_LEARNED.md](../terra/TERRA_LEARNED.md).

---

## Part 1: VPC — The Cloud Side

### What is a VPC?

A **VPC (Virtual Private Cloud)** is your isolated slice of the cloud network. Nothing in another customer's VPC can talk to yours unless you explicitly allow it.

- **One VPC** = one logical network (IP range, e.g. `10.0.0.0/16`).
- **Region-scoped:** Each VPC lives in one region.

### VPC → Subnets → Resources (Dependency Order)

Resources live **inside** a VPC. Many live in **subnets**—chunks of the VPC's IP range. Subnets are split into **public** (internet-facing) and **private** (no direct internet; DBs, app servers).

**Rule:** A subnet belongs to **exactly one VPC**. A resource (RDS, EKS, ENI) that uses subnets must use subnets from **the same VPC**.

**Dependency order:** VPC → Subnets → things that live in subnets (ENIs, DB subnet group) → higher-level resources (ALB, RDS/Aurora).

### Why Teardown Order Matters

You can't delete a VPC while something still depends on it. **Teardown order** is the reverse of creation:

1. Delete resources that use subnets (Aurora, DB subnet group; ALBs; EKS; etc.).
2. Release ENIs (often after ALB/EKS deletion; AWS may take 10–30 min).
3. Delete VPC endpoints, then subnets, then security groups, then the VPC.

---

## Part 2: Terraform State & Locks

### Plan, Apply, Destroy

| Command | What it does |
|---------|--------------|
| **plan** | "What would change?" — reads state + code, prints diff. Does **not** change cloud or state. |
| **apply** | "Make it so." — runs plan, applies changes, writes new state. |
| **destroy** | "Delete everything in state." — removes resources and state entries. |

**State** is Terraform's memory of what it created. If state and cloud get out of sync, the next plan/apply can do surprising things.

### Lock

Before **apply** or **destroy**, Terraform acquires a **lock** on the state. If someone else holds it (or a crashed run never released it), you get "Error acquiring the state lock." **Recovery:** `terragrunt force-unlock <LOCK_ID>` after confirming no other run is active.

---

## Part 3: VPC / Subnet Group Mismatch

**Problem:** State says "VPC B"; live DB subnet group is in VPC A → apply fails ("subnets not in same VPC").

**Fix options:**
- **Clean slate:** Tear down everything Terraform manages, then apply again.
- **Import:** Import existing VPC/subnet group into state so Terraform owns them.

---

## Part 4: Multi-Stack Tag Management (Durable vs Kube)

**Durable** owns VPC and subnets. **Kube** needs public subnets tagged with `kubernetes.io/role/elb=1` and `kubernetes.io/cluster/<name>=shared` so load balancers can be placed in public subnets. Kube adds these via `aws_ec2_tag`—a separate resource that tags an existing resource by ID.

**Tag drift:** Without coordination, Durable's apply would remove kube's tags. **Fix:** `lifecycle { ignore_changes = [tags] }` on subnet resources in the VPC module.

**Deep dive:** [TERRA_STACK_OWNERSHIP_AND_SHARED_RESOURCES.md](../terra/TERRA_STACK_OWNERSHIP_AND_SHARED_RESOURCES.md).

---

## Quick Reference

| Topic | Idea |
|-------|------|
| **VPC** | Isolated network; subnets are chunks; resources must use subnets from **one** VPC. |
| **Teardown order** | Reverse of creation; ENIs can lag 10–30 min after ALB/EKS delete. |
| **State** | Terraform's list of what it manages; stored remotely; must stay in sync. |
| **Lock** | Prevents concurrent writes; stale lock → `force-unlock <ID>`. |
| **Multi-stack tags** | Durable owns subnets; kube adds `kubernetes.io/*` via `aws_ec2_tag`. Use `lifecycle { ignore_changes = [tags] }` on subnets. |
