# AWS: Aurora, CloudFront, and DynamoDB placement (new project)

## 1. DynamoDB in the new project

**Same purpose as legacy.** DynamoDB in this repo is used only for **OpenTofu/Terraform state locking**: the optional `TF_LOCK_TABLE` / `TF_STATE_LOCK_TABLE` env var is passed as `dynamodb_table` in the S3 backend config (`tools/aws/backend.py`). It is not used for application data. Legacy also used DynamoDB for state locking (see commented `dynamodb_table` in legacy `root.hcl` files).

---

## 2. Where to add Aurora (PostgreSQL) and CloudFront

### Modules (reusable Terraform)

- **Best dir:** `infra-modules/aws/primitives/`
- Add e.g. `infra-modules/aws/primitives/aurora/` and `infra-modules/aws/primitives/cloudfront/` (or a combined `frontend` module that includes S3 + CloudFront if you mirror legacy).

### Deploy (stack wiring)

- **Reasonable dir:** `live-deploy-aws/scope-shared/nondurable/` for **both** Aurora and CloudFront, if you want all shared, non-VPC resources in one place.
- **Alternative for CloudFront:** a dedicated stack such as `live-deploy-aws/scope-shared/frontend/` so frontend (S3 + CloudFront) lives in one stack and stays separate from ECR/S3 data buckets.

### Aurora note

- Aurora is long-lived data. If you distinguish “durable” (VPC, secrets, things that outlive env teardowns) vs “nondurable” (recreatable), Aurora could instead live under **durable** or a dedicated **database** stack, since it depends on VPC and is not ephemeral. Putting it in `scope-shared/nondurable` is still valid if you treat “nondurable” as “shared, not per-kube/nonkube.”

---

## 3. CloudFront: two URLs (nonkube ALB vs kube NLB)

Legacy has **two separate frontend stacks**:

- **frontend-ecs:** CloudFront with origin = **ALB** (nonkube/ECS). One URL.
- **frontend-eks:** CloudFront with origin = **EKS Ingress/NLB**. Another URL.

So yes: **two different URLs**, each backed by its own CloudFront distribution (and in legacy, each has S3 + one custom origin for the ALB/NLB).

Options for the new project:

- **Option A – Two stacks:** e.g. `live-deploy-aws/scope-shared/frontend-nonkube/` and `live-deploy-aws/scope-shared/frontend-kube/`, each with its own CloudFront distribution (S3 + ALB or NLB origin). Clear separation, two URLs.
- **Option B – One stack, two distributions:** one stack under `live-deploy-aws/scope-shared/frontend/` that instantiates two CloudFront distributions (one for nonkube ALB, one for kube NLB), with different origins and URLs.
- **Option C – One distribution, two origins:** a single CloudFront distribution with two custom origins (nonkube ALB + kube NLB) and path- or host-based routing. Possible but more complex and couples both backends to one distribution.

Recommendation: **Option A or B** so you keep two distinct URLs (nonkube vs kube) and avoid coupling. Primitives live in `infra-modules/aws/primitives/`; deploy in `live-deploy-aws/scope-shared/nondurable/` or `live-deploy-aws/scope-shared/frontend/` (or two stacks under `scope-shared/` as above).

---

## 4. Implementation Plan

See **[FINAL_REFACTOR_PLAN.md](./FINAL_REFACTOR_PLAN.md)** for the consolidated refactor plan (Aurora, DB setup, PG* env vars, kube parity).
