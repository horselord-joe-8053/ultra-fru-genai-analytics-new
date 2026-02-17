# OpenTofu / Terraform: live-deploy-aws/shared/durable

Comprehensive reference for the durable shared stack and its layout. Uses OpenTofu (alias `tofu`) or Terraform.

---

## 1. live-deploy-aws layout

```text
live-deploy-aws/
├── shared/
│   ├── durable/          ← this stack (VPC, Secrets)
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   ├── README.md
│   │   ├── secrets.tf
│   │   └── variables.tf
│   └── nondurable/       ← buckets + ECR
├── kube/                 ← EKS app
└── nonkube/              ← ECS app
```

Deploy order: **durable → nondurable → (kube | nonkube)**. Teardown never destroys durable; use `tools/aws/destroy_durable.py` explicitly.

---

## 2. durable/ file structure

```mermaid
%%{init: {'themeVariables': {'fontSize': '9px'}}}%%
flowchart TB
  subgraph source["Source (committed)"]
    main["main.tf"]
    outputs["outputs.tf"]
    vars["variables.tf"]
    secrets["secrets.tf"]
    readme["README.md"]
  end
  subgraph generated["Generated (gitignored)"]
    tfdir[".terraform/"]
    lock[".terraform.lock.hcl / .tofu.lock.hcl"]
    state["*.tfstate"]
  end
  main --> tfdir
  main --> lock
  main --> state
  style source fill:#e8f5e9
  style generated fill:#fff3e0
```

---

## 3. Source files

| File | Purpose | How it's used |
|------|---------|---------------|
| **main.tf** | Root config, backend, provider, VPC module, core outputs | Entry point. Defines S3 backend (empty block, filled by deploy scripts via `-backend-config`), AWS provider, tags module, VPC module. Outputs `vpc_id`, `public_subnet_ids`, `private_subnet_ids` consumed by kube/nonkube via remote state. |
| **outputs.tf** | Placeholder for extra outputs | Currently only a comment; main outputs live in `main.tf` for convenience. |
| **variables.tf** | Variable declarations | Defines `prefix`, `env`, `aws_region`, `vpc_cidr`, `azs`, `public_subnet_cidrs`, `private_subnet_cidrs`, `allow_destroy_durable`, `tf_state_*`. Values come from env (TF_VAR_*) and deploy scripts (`-var`). |
| **secrets.tf** | Secrets Manager containers | Creates empty secret placeholders for `openai_api_key` and `db_password`. Values are set by `tools/aws/ensure_secrets.py`; Terraform never stores secret values. |
| **README.md** | Human docs | Explains what durable provisions and how to deploy via orchestrator. |

---

## 4. Generated files (gitignored)

| File / Dir | Purpose | When / how created | In this project |
|------------|---------|--------------------|-----------------|
| **.terraform/** | Provider binaries, module cache | `tofu init`. Contains provider plugins and module downloads. | **Stale** when `TF_DATA_DIR` is set. Use `tofu_data/` instead; per-stack `.terraform/` dirs removed. |
| **.terraform.lock.hcl** | Provider version lock | `tofu init`. Pins provider versions for reproducible runs. | **Gitignored** (not committed). Created per stack; used when running from that stack. |
| **terraform.tfstate** | Local state (if used) | Normally state lives in S3; local state only if backend not configured. | State is remote (S3). |
| **tofu_data/** | Shared provider cache (repo root) | Set by `TF_DATA_DIR` so all stacks share one cache. | **Canonical** location. `init_terra_upgrade_reconfigure.sh` and `tools/aws/tofu/tofu_runner.py` set `TF_DATA_DIR=$REPO_ROOT/tofu_data`. |

State is stored remotely in S3; key format: `{prefix}/{env}/aws-shared-durable.tfstate`.

---

## 5. Resource dependency flow

```mermaid
%%{init: {'themeVariables': {'fontSize': '9px'}}}%%
flowchart TB
  subgraph durable["durable stack"]
    tags["module tags"]
    vpc["module vpc"]
    openai["secret openai_api_key"]
    dbpw["secret db_password"]
  end
  tags --> vpc
  tags --> openai
  tags --> dbpw
  vpc --> out1["vpc_id, subnets"]
  openai --> out2["secret ARNs"]
  dbpw --> out2
  out1 --> kube["kube / nonkube"]
  out2 --> ensure["ensure_secrets.py"]
  style tags fill:#e3f2fd
  style vpc fill:#e8f5e9
  style openai fill:#fff3e0
  style dbpw fill:#fff3e0
```

---

## 6. How durable is invoked

| Caller | Action | Backend config |
|--------|--------|----------------|
| `tools/aws/deploy.py` | `tofu init -upgrade -reconfigure` + `tofu apply` | From `tools/aws/backend.py` via `-backend-config bucket=... -backend-config key=...` etc. |
| `tools/aws/ensure_secrets.py` | init + output read | Uses durable stack for secret ARNs |
| `tools/aws/destroy_durable.py` | `tofu destroy` | Same; requires `ALLOW_DURABLE_DESTROY=YES` and confirmation token |

**Required env vars** for init/apply (via `terra_var_handling.py` + `backend.py`): `TF_STATE_BUCKET`, `CLOUD_REGION`, `FRU_PREFIX`, `VPC_CIDR`; optionally `TF_STATE_PREFIX`, `TF_LOCK_TABLE`.

---

## 7. Module sources

```text
durable/main.tf
├── infra-modules/shared/primitives/tags
└── infra-modules/aws/primitives/vpc
```

VPC module creates: VPC, IGW, public/private subnets, route tables, NAT gateway. Uses `allow_destroy` (from `allow_destroy_durable`) to choose protected vs unprotected resources; durable passes `false` by default.

---

## 8. Quick reference

| Term | Meaning |
|------|---------|
| **durable** | Long-lived shared infra (VPC, Secrets). Never destroyed by normal teardown. |
| **nondurable** | Shared buckets + ECR. Destroyed by teardown. |
| **Backend config** | Injected by deploy scripts; `terraform init` run directly in `durable/` will prompt for S3 bucket unless you pass `-backend-config` or equivalent. |
| **ensure_secrets.py** | Populates secret values in AWS Secrets Manager; Terraform only creates the secret containers. |

---

*Related: [TERRA_LEARNED.md](TERRA_LEARNED.md), [VPC_LEARNED.md](../VPC_LEARNED.md), [infra-modules/README.md](../../../infra-modules/README.md).*
