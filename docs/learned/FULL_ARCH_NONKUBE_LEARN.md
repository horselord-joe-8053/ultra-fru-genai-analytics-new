# Full Nonkube Architecture Crash Course

A visual crash course on how **VPC, ALB, CloudFront, ECS Fargate, and Aurora** are wired together to create a fully working nonkube (ECS-based) infrastructure.

**See also:** [FULL_ARCH_KUBE_LEARN.md](FULL_ARCH_KUBE_LEARN.md), [VPC_LEARNED.md](VPC_LEARNED.md), [README_WAR_STORIES.md](../../README_WAR_STORIES.md).

---

## 1. High-Level Request Flow

```mermaid
%%{init: {'themeVariables': {'fontSize':'10px','fontFamily':'arial'}}}%%
flowchart LR
    subgraph internet["🌐 Internet"]
        user["User"]
    end

    subgraph cf["CloudFront"]
        cf_dist["CF Distribution"]
    end

    subgraph aws["AWS"]
        subgraph vpc["VPC"]
            subgraph pub["Public Subnets"]
                alb["ALB<br/><small>*.elb.amazonaws.com</small>"]
            end
            subgraph priv["Private Subnets"]
                ecs["ECS Fargate<br/>API Tasks"]
                aurora["Aurora"]
            end
        end
    end

    user -->|"HTTPS"| cf_dist
    cf_dist -->|"HTTP (origin)"| alb
    alb --> ecs
    ecs -->|"5432"| aurora

    style user fill:#e3f2fd
    style cf_dist fill:#fff3e0
    style alb fill:#ffcdd2
    style ecs fill:#c8e6c9
    style aurora fill:#e1bee7
```

| Step | Component | Protocol | Purpose |
|------|-----------|----------|---------|
| 1 | User → CloudFront | HTTPS | SSL termination at edge |
| 2 | CloudFront → ALB | HTTP | Origin fetch (ALB listens on 80) |
| 3 | ALB → API tasks | HTTP:80 | Load balance to fru-api containers |
| 4 | API tasks → Aurora | TCP:5432 | DB queries |

---

## 2. Terraform Stack Dependency Order

```mermaid
%%{init: {'themeVariables': {'fontSize':'9px'}}}%%
flowchart TB
    subgraph durable["shared/durable"]
        vpc["VPC"]
        aurora_mod["Aurora"]
    end

    subgraph nondurable["shared/nondurable"]
        ecr["ECR"]
        s3["S3 Delta"]
    end

    subgraph nonkube["nonkube"]
        ecs_mod["ECS + ALB"]
        cf_mod["CloudFront"]
        eb["EventBridge"]
        sg_rule["Aurora←ECS SG rule"]
    end

    vpc --> aurora_mod
    vpc --> ecs_mod
    ecr --> ecs_mod
    s3 --> ecs_mod
    aurora_mod --> sg_rule
    ecs_mod --> sg_rule
    ecs_mod --> cf_mod
    ecs_mod --> eb

    style vpc fill:#e3f2fd
    style aurora_mod fill:#e1bee7
    style ecs_mod fill:#c8e6c9
    style cf_mod fill:#fff3e0
```

| Stack | Creates | Depends On |
|-------|---------|------------|
| **shared/durable** | VPC, subnets, NAT, Aurora, DB subnet group | — |
| **shared/nondurable** | ECR, S3 buckets | — |
| **nonkube** | ECS cluster, ALB, API service, EventBridge, CloudFront | durable, nondurable |

---

## 3. VPC & Subnet Layout

```mermaid
%%{init: {'themeVariables': {'fontSize':'9px'}}}%%
flowchart TB
    subgraph vpc["VPC (10.0.0.0/16)"]
        subgraph pub["Public Subnets"]
            pub1["pub-0<br/>10.0.1.0/24"]
            pub2["pub-1<br/>10.0.2.0/24"]
        end
        subgraph priv["Private Subnets"]
            priv1["priv-0<br/>10.0.11.0/24"]
            priv2["priv-1<br/>10.0.12.0/24"]
        end
        igw["IGW"]
        nat["NAT GW"]
    end

    pub1 --> igw
    pub2 --> igw
    priv1 -.->|"0.0.0.0/0"| nat
    priv2 -.->|"0.0.0.0/0"| nat
    nat --> pub1

    style pub fill:#ffcdd2
    style priv fill:#c8e6c9
```

| Subnet Type | Used By | Route to Internet |
|-------------|---------|-------------------|
| **Public** | ALB | IGW (direct) |
| **Private** | ECS Fargate tasks (API + Spark), Aurora | NAT GW (outbound only) |

**ALB placement:** ALB is created by Terraform in **public subnets** (`var.public_subnet_ids`). No K8s; DNS is available immediately after apply.

---

## 4. End-to-End Data Path (Detailed)

```mermaid
%%{init: {'themeVariables': {'fontSize':'8px'}}}%%
flowchart TB
    subgraph ext["External"]
        u["User Browser"]
    end

    subgraph cf["CloudFront"]
        o1["S3 Origin<br/>/index.html"]
        o2["API Origin<br/>/health, /query"]
    end

    subgraph vpc["VPC"]
        subgraph pub["Public"]
            alb["ALB<br/>DNS from Terraform"]
        end
        subgraph priv["Private"]
            task["ECS API Task"]
            db["Aurora"]
        end
    end

    u -->|"1"| cf
    cf -->|"2a"| o1
    cf -->|"2b"| o2
    o2 -->|"3"| alb
    alb -->|"4"| task
    task -->|"5"| db

    style u fill:#e3f2fd
    style cf fill:#fff3e0
    style alb fill:#ffcdd2
    style task fill:#c8e6c9
    style db fill:#e1bee7
```

| # | Path | Notes |
|---|------|-------|
| 1 | User → CloudFront | `https://d123.cloudfront.net` |
| 2a | CF → S3 | Static frontend (index.html, assets) |
| 2b | CF → API origin | `/health`, `/query`, `/analytics` |
| 3 | CF → ALB | `http://fru-dev-alb-xxx.elb.us-east-1.amazonaws.com` |
| 4 | ALB → ECS task | Target group → Fargate task IP |
| 5 | Task → Aurora | PGHOST from task env (Secrets Manager) |

---

## 5. No DNS Propagation Delay (vs Kube)

```mermaid
%%{init: {'themeVariables': {'fontSize':'9px'}}}%%
flowchart LR
    subgraph tf["Terraform Apply"]
        ecs_mod["ECS module"]
    end

    subgraph aws["AWS"]
        alb["ALB created"]
        dns["ALB DNS<br/>immediate"]
    end

    ecs_mod -->|"single apply"| alb
    alb -->|"ready"| dns

    style ecs_mod fill:#c8e6c9
    style alb fill:#ffcdd2
    style dns fill:#e1bee7
```

| Aspect | Nonkube (ECS) | Kube (EKS) |
|--------|---------------|------------|
| **Load balancer** | ALB (Terraform) | NLB (K8s Service) |
| **DNS availability** | Immediate | 1–2 min propagation |
| **CloudFront wiring** | Single apply (alb_dns_name from output) | Two-phase (ingress_hostname null → re-apply) |
| **Extra wait** | None | `wait_for_dns_resolvable` |

---

## 6. File Structure

```
fru-genai-analytics-new/
├── live_deploy_aws/
│   ├── shared/
│   │   ├── durable/          # VPC, Aurora (apply first)
│   │   │   ├── main.tf
│   │   │   └── outputs: vpc_id, private_subnet_ids, aurora_endpoint
│   │   └── nondurable/       # ECR, S3 (apply second)
│   │       ├── main.tf
│   │       └── outputs: ecr_app_url, ecr_spark_url, delta_bucket
│   └── nonkube/              # ECS, ALB, CloudFront (apply third)
│       ├── main.tf
│       └── outputs: alb_dns_name, cloudfront_domain_name, frontend_s3_bucket_id
│
├── infra_modules/
│   └── aws/
│       ├── primitives/
│       │   ├── vpc/          # VPC, subnets, NAT, IGW
│       │   ├── aurora/       # Aurora Serverless v2
│       │   └── cloudfront/   # CF dist, S3 frontend, API origin
│       └── ecs/              # ECS cluster, ALB, API service, Spark schedule
│           ├── main.tf       # ALB, target group, ECS service, EventBridge
│           └── outputs.tf    # alb_dns_name, ecs_cluster_name, spark_task_definition_arn
│
└── tools/aws/
    ├── deploy.py            # run_ecs_bootstrap (one-off Spark task)
    ├── bootstrap_helpers.py  # check_ecs_bootstrap_succeeded
    └── teardown.py          # Pre-destroy: EventBridge, scale to 0, drain tasks
```

---

## 7. Deploy Sequence (Nonkube)

| Phase | Action | Tool / Resource |
|-------|--------|-----------------|
| 1 | Apply shared/durable | `tofu apply` |
| 2 | Apply shared/nondurable | `tofu apply` |
| 3 | Ensure secrets (PGPASSWORD, etc.) | `ensure_secrets.py` |
| 4 | Build & push images | `build_and_push_images.py` |
| 5 | Apply nonkube stack | `tofu apply` (ALB + ECS + CF in one pass) |
| 6 | Deploy frontend to S3, invalidate CF | `deploy_frontend_to_s3` |
| 7 | Run ECS bootstrap (one-off Spark task) | `run_ecs_bootstrap` |

**Bootstrap:** ECS RunTask with Spark image, command override to `run_analytics.py`. Idempotent: skips if `check_ecs_bootstrap_succeeded` finds success pattern in logs.

---

## 8. Teardown Sequence (Nonkube)

| Step | Action | Why |
|------|--------|-----|
| 1 | Disable EventBridge rule | Stop Spark schedule from firing |
| 2 | Remove EventBridge targets | Required before delete |
| 3 | Delete EventBridge rule | Orphan safety if state empty |
| 4 | Scale ECS service to 0 | Stop API tasks |
| 5 | Stop remaining tasks | Drain EventBridge-triggered Spark tasks |
| 6 | Wait for cluster empty | ClusterContainsTasksException otherwise |
| 7 | `tofu destroy` nonkube stack | ECS, ALB, EventBridge, CloudFront |

---

## 9. ECS Components

```mermaid
%%{init: {'themeVariables': {'fontSize':'9px'}}}%%
flowchart TB
    subgraph ecs["ECS Cluster"]
        svc["API Service<br/>desired_count"]
        tg["Target Group"]
    end

    subgraph lb["ALB"]
        listener["HTTP:80"]
    end

    subgraph eb["EventBridge"]
        rule["Cron rule"]
    end

    subgraph spark["Spark tasks"]
        bootstrap["Bootstrap RunTask<br/>(deploy.py)"]
        cron["Scheduled RunTask<br/>(EventBridge)"]
    end

    listener --> tg
    tg --> svc
    rule --> cron
    cron --> ecs
    bootstrap --> ecs

    style svc fill:#c8e6c9
    style listener fill:#ffcdd2
    style rule fill:#e1bee7
```

| Component | Type | Purpose |
|-----------|------|---------|
| **API service** | ECS service | Long-running fru-api containers |
| **ALB + target group** | Application LB | Route HTTP to API tasks |
| **Bootstrap** | ECS RunTask | One-off Spark `run_analytics.py` |
| **Spark schedule** | EventBridge → RunTask | Cron-triggered Spark jobs |

---

## 10. Security Groups

| SG | Source | Target | Port | Purpose |
|----|--------|--------|------|---------|
| ALB SG | 0.0.0.0/0 | ALB | 80 | Internet → ALB |
| ECS tasks SG | ALB SG | Tasks | 5001 | ALB → API containers |
| Aurora SG | ECS tasks SG | Aurora | 5432 | API tasks → DB |

---

## 11. Quick Reference Table

| Concept | Summary |
|--------|---------|
| **VPC** | Same as kube: one VPC; public + private subnets; NAT for private |
| **ALB** | Terraform-created in public subnets; DNS ready immediately |
| **CloudFront** | S3 + API origin; API origin = alb_dns_name from ECS module |
| **ECS** | Fargate tasks in private subnets; API service + RunTask for Spark |
| **Aurora** | Private subnets; ingress from ECS tasks SG only |
| **Bootstrap** | ECS RunTask (Spark run_analytics); idempotent via log check |
| **Spark schedule** | EventBridge cron → ECS RunTask (not ECS service) |

---

## 12. Kube vs Nonkube Comparison

| Aspect | Kube | Nonkube |
|--------|------|---------|
| **Compute** | EKS + nodes + pods | ECS Fargate |
| **Load balancer** | NLB (K8s Service) | ALB (Terraform) |
| **DNS timing** | 1–2 min propagation | Immediate |
| **Bootstrap** | K8s Job | ECS RunTask |
| **Spark schedule** | K8s CronJob | EventBridge → RunTask |
| **Apply phases** | Two (ingress_hostname) | One |
| **Pre-destroy** | Delete LB svc, CronJob, Job, namespace | EventBridge, scale to 0, drain |

---

## 13. Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| ClusterContainsTasksException | EKS/ECS destroy fails | Pre-destroy: drain tasks first |
| EventBridge fires during teardown | New Spark tasks block destroy | Disable rule before scale/drain |
| DB password mismatch | /health returns disconnected | `ensure_secrets` + redeploy |
| Bootstrap not idempotent | Re-runs every deploy | `check_ecs_bootstrap_succeeded` skips if done |

---

*Doc: `docs/learned/FULL_ARCH_NONKUBE_LEARN.md`. Related: [FULL_ARCH_KUBE_LEARN.md](FULL_ARCH_KUBE_LEARN.md), [VPC_LEARNED.md](VPC_LEARNED.md), [README_WAR_STORIES.md](../../README_WAR_STORIES.md).*
