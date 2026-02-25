# Kubernetes Ingress & Load Balancer Crash Course

A short, project-anchored guide to Ingress, IngressClass, controllers, and how the LB appears for EKS.

> **Note:** This doc describes both (1) our **current** kube deploy using `fru-api-svc` (type LoadBalancer) directly, and (2) an NGINX Ingress–based flow for reference.

---

## 0. Kube Load Balancer Choice: Classic ELB vs NLB (Project Reality)

Our kube API is exposed via `fru-api-svc` (type LoadBalancer), **not** NGINX Ingress. We support two load balancer tracks, selected by the `--elb` flag at deploy time.

### 0.1 The Two Tracks

| Track | Flag | Manifest | Who creates LB | LB type |
|-------|------|----------|----------------|---------|
| **NLB** (default) | *no* `--elb` | `api-service.yaml` | AWS Load Balancer Controller | Network Load Balancer |
| **Classic ELB** | `--elb` | `api-service-elb.yaml` | In-tree cloud provider | Classic ELB (legacy) |

#### What NLB and Classic ELB Are

- **Classic ELB** — AWS’s original load balancer (pre-2016). Layer 4/7, one product for TCP/HTTP/HTTPS. Still supported but legacy. Creates `k8s-elb-{hex}` security groups. DNS: `*.elb.amazonaws.com`.
- **NLB (Network Load Balancer)** — Newer AWS LB (2017+). Layer 4 only, lower latency, higher throughput, static IPs, better for TCP. Also uses `*.elb.amazonaws.com` DNS. Preferred for API traffic.

#### What “In-Tree” vs “Out-of-Tree” Means

When you create a Kubernetes Service with `type: LoadBalancer`, *something* must call AWS APIs to create the real load balancer. There are two possible reconcilers:

| Reconciler | Where it lives | What it creates |
|------------|----------------|-----------------|
| **In-tree cloud provider** | Code inside the main Kubernetes repo (`kube-controller-manager`). Built-in, always present on EKS. | Classic ELB + `k8s-elb-*` security groups |
| **AWS Load Balancer Controller** (out-of-tree) | Separate controller running as pods in the cluster. Installed via Helm. | NLB, ALB (depending on annotations) |

- **In-tree** = “in the Kubernetes tree” — part of core K8s.
- **Out-of-tree** = “outside the tree” — a separate project that watches K8s resources and talks to AWS.

#### How the Annotations Wire Things Together

The annotations on the Service decide:

1. **Which reconciler handles the Service** — This is the main wiring.
2. **How the LB is configured** — Scheme, target type, etc.

| Annotation | Meaning for wiring |
|------------|--------------------|
| `service.beta.kubernetes.io/aws-load-balancer-type: external` | **Hand this Service to the AWS Load Balancer Controller.** The in-tree provider *ignores* Services with this annotation. Without it, the in-tree handles the Service and creates a Classic ELB. |
| `service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing` | LB is reachable from the internet (vs `internal` for private subnets). CloudFront must reach the API origin from the internet. |
| `service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: instance` | (NLB only.) Route traffic to node IPs (instance mode) vs pod IPs (ip mode). We use `instance` for compatibility. |

**The critical wiring:** `aws-load-balancer-type: external` is the switch. Present → AWS Load Balancer Controller reconciles → NLB. Absent → in-tree reconciles → Classic ELB.

**Setup requirements:**

- **Classic ELB track:** No extra setup. The in-tree provider is built into EKS. Apply `api-service-elb.yaml` and the LB appears.
- **NLB track:** The AWS Load Balancer Controller must be installed in the cluster first (Phase 9.5). Without it, a Service with `aws-load-balancer-type: external` would have no reconciler and would stay in `Pending`.

### 0.2 How the Choice Flows Through Deploy

```
deploy.py --scope kube [--elb]
    │
    ├── doctor.py [--elb]  →  NLB track: requires eksctl, helm (for controller install)
    │
    └── deploy_kube.py
            │
            ├── Phase 9.5: Install AWS Load Balancer Controller  (skipped when --elb)
            │
            └── kube_apply.py [--elb]
                    │
                    └── api_svc_manifest = "api-service-elb.yaml" if args.elb else "api-service.yaml"
```

- **With `--elb`:** Uses `api-service-elb.yaml`. No `aws-load-balancer-type: external` → in-tree cloud provider reconciles it → creates **Classic ELB**. No controller install needed.
- **Without `--elb`:** Uses `api-service.yaml`. Has `aws-load-balancer-type: external` → AWS Load Balancer Controller reconciles it → creates **NLB**. Phase 9.5 installs the controller before kube_apply.

### 0.3 Manifest Differences

**`api-service.yaml` (NLB track):**
```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
  service.beta.kubernetes.io/aws-load-balancer-type: external
  service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: instance
```

**`api-service-elb.yaml` (Classic ELB track):**
```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
# No aws-load-balancer-type → in-tree creates Classic ELB
```

### 0.4 When to Use Each

| Use case | Track |
|----------|-------|
| **Default, recommended** | NLB (no `--elb`) — modern, better performance, controller installed automatically |
| **Fallback / pre-migration** | Classic ELB (`--elb`) — no eksctl/helm, in-tree only; reverts to pre-migration behavior |
| **Orphan cleanup after migration** | After switching to NLB, old Classic ELBs + `k8s-elb-*` SGs become orphans; run `remove_for_orphans_data.py` |

### 0.5 Key Files

| File | Purpose |
|------|---------|
| `infra_terraform/modules/cloud_shared/k8s/api-service.yaml` | NLB manifest (default) |
| `infra_terraform/modules/cloud_shared/k8s/api-service-elb.yaml` | Classic ELB manifest (used with `--elb`) |
| `tools/aws/kube/kube_apply.py` | Selects manifest: `api-service-elb.yaml` if `args.elb` else `api-service.yaml` |
| `tools/aws/kube/deploy_kube.py` | Phase 9.5: installs AWS Load Balancer Controller when not `--elb` |
| `tools/aws/kube/install_aws_load_balancer_controller.py` | Python script that installs the controller (eksctl IAM, helm chart) |

**NLB controller install:** Runs automatically during deploy (Phase 9.5) when not using `--elb`. Implemented 2026-02.

### 0.6 NLB Migration Steps (Classic ELB → NLB)

1. **Deploy kube (NLB track):** `python tools/aws/deploy.py --scope kube --env dev` — controller installs automatically.
2. **Verify:** `python tools/aws/scope_shared/verify/verify_all_deploy.py --scope kube --env dev`
3. **Orphan scan:** `PYTHONPATH=$(pwd) python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py --cloud-regions us-east-1 --env dev --prefix fru` (omit `--elb` for NLB track)
4. **Orphan removal:** Dry-run then `remove_for_orphans_data.py` for Classic ELBs and `k8s-elb-*` SGs
5. **Re-verify:** Same verify command

---

## 1. Objects and What They Do

> **Our API:** We use `fru-api-svc` (type LoadBalancer) directly—no Ingress. See **Section 0** for the Classic ELB vs NLB choice. The table below describes the NGINX Ingress flow for reference.

| Object | What it is | In our project |
|--------|------------|----------------|
| **Service** (type: LoadBalancer) | K8s object that exposes pods. When `type: LoadBalancer`, the **cloud** (e.g. AWS) creates a real load balancer (NLB/ALB/Classic ELB) and puts its DNS in the Service’s `.status.loadBalancer.ingress`. | **API:** `fru-api-svc` in `fru-kube` (see Section 0). **NGINX flow:** `ingress-nginx-controller` Service → NLB. |
| **Ingress** | K8s object that describes **routing rules** (paths → backend Service). It does **not** create a load balancer by itself. | Our app Ingress: paths `/query`, `/analytics`, `/health`, `/version` → Service `fru-api`. |
| **IngressClass** | K8s object that names a **class** (e.g. `fru-nginx-cls`) and points to the **controller** that implements it (e.g. NGINX). | We use class name `fru-nginx-cls`; the NGINX Helm chart creates this IngressClass and registers itself. |
| **Ingress Controller** | A **process** (running as pods) that watches Ingress and IngressClass resources and configures a **proxy** (e.g. NGINX). It also **fills** Ingress `.status.loadBalancer` with the LB hostname (from its own Service). | NGINX Ingress Controller: installed via Helm; one controller, one NLB; all Ingresses with `ingressClassName: fru-nginx-cls` use it. |

---

## 2. How They Connect (the “link” is the class name)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'11px'}}}%%
flowchart LR
  subgraph helm["Helm install"]
    V[ingress-nginx-values-eks.yaml]
    V -->|ingressClassResource.name| IC[IngressClass fru-nginx-cls]
    V -->|controller.service| SVC[Service LoadBalancer]
  end
  subgraph app["App manifests"]
    T[ingress.template.yaml]
    T -->|ingressClassName| ING[Ingress fru-nginx-cls]
  end
  IC -.->|owned by| CTRL[NGINX Controller]
  SVC -->|AWS creates| NLB[NLB]
  CTRL -->|watches| ING
  CTRL -->|copies NLB hostname to| ING
  ING -->|routes to| API[fru-api Service]
  style IC fill:#e8f5e9
  style ING fill:#e8f5e9
  style NLB fill:#e3f2fd
  style CTRL fill:#fff3e0
```

- **Controller side:** Helm values set `controller.ingressClassResource.name: fru-nginx-cls`. The chart creates an **IngressClass** with that name and the NGINX controller **owns** it.
- **App side:** Ingress template sets `spec.ingressClassName: fru-nginx-cls`. That Ingress is **handled by** the controller that owns the IngressClass `fru-nginx-cls`.
- **No direct reference** between the two YAMLs; the **same string** (`fru-nginx-cls`) is the only link.

---

## 3. Request Path (EKS with CloudFront)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'11px'}}}%%
sequenceDiagram
  participant U as User
  participant CF as CloudFront
  participant NLB as NLB
  participant NGINX as NGINX Controller
  participant ING as App Ingress
  participant SVC as fru-api Service
  participant P as Pods

  U->>CF: HTTPS /query
  CF->>NLB: HTTP (origin)
  NLB->>NGINX: HTTP
  NGINX->>ING: match path /query
  ING->>SVC: route to fru-api:80
  SVC->>P: to backend pods
  P-->>U: response
```

- **NLB** is created by AWS for the NGINX controller’s **Service** (type LoadBalancer).
- **NGINX** is the only thing that receives traffic from the NLB; it uses **Ingress** rules to send requests to the right Service (e.g. `fru-api`).

---

## 4. Where Things Are Defined (our repo)

| What | Where |
|------|--------|
| Controller class name | `module_infra_kubetypes/kube/common/ingress-nginx-values-eks.yaml` (and `-local.yaml`): `controller.ingressClassResource.name: fru-nginx-cls` |
| App Ingress class | `module_infra_kubetypes/kube/common/templates/ingress.template.yaml`: `spec.ingressClassName: fru-nginx-cls` |
| Controller install | `module_infra_kubetypes/kube/aws/helpers/install-ingress-nginx-eks.sh` (Helm with EKS values) |
| App Ingress apply | Generated from template → `generated/ingress-generated.yaml`; applied by `apply_kubernetes_manifests()` in deploy flow |

---

## 5. One Controller, One NLB

- We install **one** NGINX Ingress Controller; it has **one** LoadBalancer Service → **one** NLB.
- **All** Ingresses with `ingressClassName: fru-nginx-cls` are satisfied by that controller and share that NLB.
- For a given class name, there should be **one** controller; otherwise behavior is undefined.

---

## 6. Order of Operations (EKS deploy)

1. **Install NGINX** (Helm + `ingress-nginx-values-eks.yaml`) → controller runs, its Service gets NLB, IngressClass `fru-nginx-cls` exists.
2. **Apply app manifests** (including generated Ingress) → Ingress has `ingressClassName: fru-nginx-cls`; NGINX adopts it and copies NLB hostname to Ingress `.status`.
3. **Update CloudFront** (script reads Ingress `.status.loadBalancer.ingress[0].hostname`) → origin set to NLB DNS.

The app Ingress does **not** reference the NLB directly; the **controller** fills `.status` after it adopts the Ingress.

---

## 7. Troubleshooting: ErrImagePull / ImagePullBackOff

If the fru-api deployment shows `ErrImagePull` or `ImagePullBackOff`, the nodes cannot pull the image from ECR.

**Common cause:** The deployment image tag was **never pushed** to ECR. This happens if you re-run deploy with `--skip-build` after a failure: the script generates a **new** tag (timestamp-based), so the deployment points to a tag that doesn’t exist in ECR.

**Verify:**
- `kubectl describe pod -n fru-api-dev -l app=fru-api` — see exact pull error.
- `aws ecr list-images --repository-name fru-api --region us-east-1 --profile admin` — list tags in ECR.

**Fix:**
- **Option A:** Run full deploy (no `--skip-build`) so the same tag is built, pushed, and applied.
- **Option B:** With `--skip-build`, the script now defaults to `IMAGE_TAG=latest` (build-push-ecr pushes both the git tag and `latest`). If you see ErrImagePull, ensure a full deploy has run at least once so `latest` exists in ECR, or set `IMAGE_TAG=<existing-tag>` (or `CONTAINER_IMAGE`) before running deploy with `--skip-build`.
