# Architecture: AWS & GCP — General Reference

Colored, detailed architecture diagrams for all four deployment modes. Based on deployment scripts and `infra_terraform/live_deploy/{aws,gcp}/` stacks. **Entrypoint:** `orchestrator.py deploy --provider {aws,gcp} --scope {kube,nonkube,all} [--cloud-region REGION]`.

**Stacks:** `infra_terraform/live_deploy/{aws,gcp}/scope_shared/{durable,durable_with_cooloff,nondurable}`, `{aws,gcp}/{kube,nonkube}`.

---

## 1. AWS Kube (EKS)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'10px', 'fontFamily':'sans-serif'}, 'flowchart': {'nodeSpacing':18, 'rankSpacing':22}}}%%
flowchart TB
    subgraph ext["🌐 Internet"]
        U1["User"]
    end

    subgraph cf1["CloudFront"]
        CF1["CF Distribution"]
    end

    subgraph aws1["AWS VPC"]
        subgraph pub1["Public Subnets"]
            LB1["NLB / Classic ELB<br/><small>*.elb.amazonaws.com</small>"]
        end
        subgraph priv1["Private Subnets"]
            EKS1["EKS Nodes"]
            POD1["fru-api Pods"]
            AUR1["Aurora"]
        end
    end

    U1 -->|"1. HTTPS"| CF1
    CF1 -->|"2. HTTP origin"| LB1
    LB1 -->|"3. TCP:80"| EKS1
    EKS1 --> POD1
    POD1 -->|"4. 5432"| AUR1

    style U1 fill:#e3f2fd
    style CF1 fill:#fff3e0
    style LB1 fill:#ffcdd2
    style POD1 fill:#c8e6c9
    style AUR1 fill:#e1bee7
```

**Numerated flow:**
1. User → CloudFront (HTTPS, SSL termination at edge).
2. CloudFront → NLB/ELB (HTTP; LB has no ACM cert).
3. LB → EKS nodes (NodePort / kube-proxy) → fru-api pods.
4. Pods → Aurora (PGHOST from Secrets Manager).

**Stack order:** durable → durable_with_cooloff → nondurable → kube. Kube creates EKS, CloudFront, frontend S3; subnet tags for LB placement. See [KUBE_LB.md](KUBE_LB.md).

---

## 2. AWS Nonkube (ECS)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'10px', 'fontFamily':'sans-serif'}, 'flowchart': {'nodeSpacing':18, 'rankSpacing':22}}}%%
flowchart TB
    subgraph ext2["🌐 Internet"]
        U2["User"]
    end

    subgraph cf2["CloudFront"]
        CF2["CF Distribution"]
    end

    subgraph aws2["AWS VPC"]
        subgraph pub2["Public Subnets"]
            ALB2["ALB<br/><small>*.elb.amazonaws.com</small>"]
        end
        subgraph priv2["Private Subnets"]
            ECS2["ECS Fargate<br/>API Tasks"]
            AUR2["Aurora"]
        end
    end

    U2 -->|"1. HTTPS"| CF2
    CF2 -->|"2. HTTP origin"| ALB2
    ALB2 -->|"3. HTTP:80"| ECS2
    ECS2 -->|"4. 5432"| AUR2

    style U2 fill:#e3f2fd
    style CF2 fill:#fff3e0
    style ALB2 fill:#ffcdd2
    style ECS2 fill:#c8e6c9
    style AUR2 fill:#e1bee7
```

**Numerated flow:**
1. User → CloudFront (HTTPS).
2. CloudFront → ALB (HTTP; Terraform-created in public subnets).
3. ALB → ECS Fargate API tasks (target group).
4. Tasks → Aurora (PGHOST from task env via Secrets Manager).

**Stack order:** durable → durable_with_cooloff → nondurable → nonkube. Nonkube creates ECS cluster, ALB, EventBridge (Spark schedule), CloudFront. **DNS:** ALB hostname available immediately (no LB propagation delay).

---

## 3. GCP Kube (GKE)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'10px', 'fontFamily':'sans-serif'}, 'flowchart': {'nodeSpacing':18, 'rankSpacing':22}}}%%
flowchart TB
    subgraph ext3["🌐 Internet"]
        U3["User"]
    end

    subgraph cdn3["Cloud CDN"]
        CDN3["CDN Distribution"]
    end

    subgraph gcp3["GCP VPC"]
        subgraph gke3["GKE Cluster"]
            LB3["LoadBalancer Svc<br/><small>or Ingress</small>"]
            POD3["fru-api Pods"]
        end
        SQL3["Cloud SQL<br/><small>private IP</small>"]
    end

    U3 -->|"1. HTTPS"| CDN3
    CDN3 -->|"2. HTTP origin"| LB3
    LB3 -->|"3"| POD3
    POD3 -->|"4. VPC Connector"| SQL3

    style U3 fill:#e3f2fd
    style CDN3 fill:#fff3e0
    style LB3 fill:#ffcdd2
    style POD3 fill:#c8e6c9
    style SQL3 fill:#e1bee7
```

**Numerated flow:**
1. User → Cloud CDN (HTTPS).
2. Cloud CDN → GKE LoadBalancer Service or Ingress (HTTP).
3. LB → fru-api pods.
4. Pods → Cloud SQL via VPC connector (private IP).

**Stack order:** durable → durable_with_cooloff → nondurable → kube. GKE uses `api-service-gke.yaml`; Cloud SQL via VPC connector. Delta in GCS.

---

## 4. GCP Nonkube (Cloud Run)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'10px', 'fontFamily':'sans-serif'}, 'flowchart': {'nodeSpacing':18, 'rankSpacing':22}}}%%
flowchart TB
    subgraph ext4["🌐 Internet"]
        U4["User"]
    end

    subgraph cdn4["Cloud CDN"]
        CDN4["CDN Distribution"]
    end

    subgraph gcp4["GCP"]
        CR4["Cloud Run<br/>API Service"]
        VPC4["VPC Connector"]
        SQL4["Cloud SQL<br/><small>private IP</small>"]
    end

    U4 -->|"1. HTTPS"| CDN4
    CDN4 -->|"2. *.run.app"| CR4
    CR4 -->|"3. via connector"| VPC4
    VPC4 -->|"4. private IP"| SQL4

    style U4 fill:#e3f2fd
    style CDN4 fill:#fff3e0
    style CR4 fill:#c8e6c9
    style VPC4 fill:#e3f2fd
    style SQL4 fill:#e1bee7
```

**Numerated flow:**
1. User → Cloud CDN (HTTPS).
2. Cloud CDN → Cloud Run API service (`*.run.app`; built-in LB).
3. API → VPC connector (bridges Cloud Run to VPC).
4. VPC connector → Cloud SQL (private IP).

**Stack order:** durable → durable_with_cooloff → nondurable → nonkube. Cloud Run runs outside VPC; VPC connector bridges to Cloud SQL. See [GCP_API_CLOUD_SQL_WIRING.md](GCP_API_CLOUD_SQL_WIRING.md).

---

## 5. Pattern: API + Frontend on Cloud

| Aspect | AWS | GCP |
|--------|-----|-----|
| **Frontend** | S3 + CloudFront | GCS + Cloud CDN |
| **API (nonkube)** | ECS Fargate + ALB | Cloud Run |
| **API (kube)** | EKS + NLB/ELB | GKE + LB Svc |
| **DB** | Aurora | Cloud SQL |
| **Delta** | S3 | GCS |
| **Spark schedule** | EventBridge (nonkube) / CronJob (kube) | Cloud Scheduler (nonkube) / CronJob (kube) |

**Common pattern:** CDN → API origin (LB or serverless) → compute (containers) → DB. Secrets from provider secret store (Secrets Manager / Secret Manager).

---

## 6. Extensibility to Other Providers

When adding Oracle, Azure, Huawei, or another provider:

1. **Mirror stack layout:** `live_deploy/<provider>/scope_shared/{durable,durable_with_cooloff,nondurable}`, `{provider}/{kube,nonkube}`.
2. **Map components:** VPC, managed DB, object storage, container runtime, LB, CDN, secrets. See [COMMON_CLOUD_COMPONENTS.md](COMMON_CLOUD_COMPONENTS.md).
3. **DB access:** Decide if deploy host can reach DB directly (AWS-style) or needs in-VPC/serverless helper (GCP-style).
4. **Orchestrator:** Add provider branch in `orchestrator.py`; route to `tools/<provider>/deploy.py`, `teardown.py`, etc.

---

## 7. Optimization Opportunities

| Opportunity | Description |
|-------------|-------------|
| **Content-based build skip** | Hash build context; skip Docker build when unchanged. See [DEPLOY_BUILD_DOCKER.md](DEPLOY_BUILD_DOCKER.md). |
| **Single kube apply** | When LB hostname known before first apply, skip second Terraform apply. |
| **Skip import + apply** | When plan shows no changes, skip import and apply for that stack. |
| **VPC tag lifecycle** | `lifecycle { ignore_changes = [tags] }` on subnets to avoid durable/kube tag drift. |
| **IRSA for EKS** | Replace static keys in EKS pods with IAM Roles for Service Accounts. |

---

## 8. Related Docs

- [KUBE_LB.md](KUBE_LB.md) — NLB vs Classic ELB for AWS kube
- [VPC_AND_NETWORK.md](VPC_AND_NETWORK.md) — VPC concepts
- [ANALYTICS_AND_DATA.md](ANALYTICS_AND_DATA.md) — Shared Delta + batch_analytics
