# Multi-Region AWS Deployment

Evaluation of how to add multi-region deployment for AWS (e.g. us-east-1, us-west-2).

> **Note:** Run scripts with `PYTHONPATH=.` from project root, e.g. `PYTHONPATH=. python tools/aws/teardown.py --scope all --env dev --non-interactive`

## Options

### Option A: Region as Directory

```
infra_terraform/live_deploy/aws/
├── us-east-1/
│   ├── kube/
│   ├── nonkube/
│   └── scope_shared/
└── us-west-2/
    ├── kube/
    ├── nonkube/
    └── scope_shared/
```

**Pros:** Clear separation, region-specific configs, explicit isolation.  
**Cons:** Duplication of Terraform files, more maintenance.

### Option B: Region as Parameter (Recommended for Symmetrical Infra)

Keep flat layout; pass `--region` to the entry point script:

```
infra_terraform/live_deploy/aws/
├── kube/
├── nonkube/
└── scope_shared/
```

State is already keyed by region: `.../${env}/${region}/aws-*.tfstate`.

**Pros:** Single source of truth, no duplication, easier maintenance.  
**Cons:** Must parameterize region-specific values (e.g. AZs).

## Recommendation

For **symmetrical infrastructure** (same config across regions), use **Option B** (region as parameter):

1. **No duplication** – One set of Terraform files.
2. **Less maintenance** – Single place to update.
3. **State isolation** – Each region already uses its own state file.
4. **Script support** – Deploy/teardown already accept `--region`.

### Usage

```bash
python tools/aws/deploy.py --scope all --env dev --region us-east-1
python tools/aws/deploy.py --scope all --env dev --region us-west-2
```

Or add `--regions us-east-1,us-west-2` to loop over regions in one run.

### Parameterization Required

1. **AZs** – Replace hardcoded `azs=["us-east-1a","us-east-1b"]` with:
   - `data "aws_availability_zones" "available" { state = "available" }`, or
   - A small map: `var.region -> [az1, az2]`
2. **Region** – Pass `aws_region` (or equivalent) into all stacks; scripts already support `--region`.

## When to Use Option A

Use directory-per-region when:
- Regions need different configs (instance types, AZs, resource limits).
- You want explicit separation for team/organization.
- You want to prevent accidental cross-region apply.
