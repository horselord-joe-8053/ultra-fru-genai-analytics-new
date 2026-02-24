# Kube Load Balancer Migration: Classic ELB → NLB

Steps to migrate from in-tree Classic ELB to AWS Load Balancer Controller NLB, then remove orphaned Classic ELBs.

**Implemented:** NLB controller install runs **automatically** during deploy when not using `--elb`. See [REFACTOR_PLAN_NLB_DEPLOY_INTEGRATION.md](REFACTOR_PLAN_NLB_DEPLOY_INTEGRATION.md).

## Prerequisites

- AWS credentials configured
- `kubectl`, `eksctl`, `helm` (doctor checks these for NLB track)
- For Classic ELB track: use `--elb` to skip controller install

## Step 1: Deploy kube scope (NLB track)

The deploy flow installs the AWS Load Balancer Controller automatically (Phase 9.5) before kube_apply. No manual install step needed.

The `api-service.yaml` (default, no `--elb`) has:

```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
  service.beta.kubernetes.io/aws-load-balancer-type: external
```

## Step 2: Deploy kube scope

```bash
python tools/aws/deploy.py --scope kube --env dev
# or: python orchestrator.py deploy --scope kube --env dev
```

The deploy will:
- Install AWS Load Balancer Controller (if NLB track)
- Apply kube_apply (bootstrap + schedule)
- Poll for LB hostname after kube_apply
- If hostname **changed** (Classic → NLB), run second tofu apply to wire CloudFront to the new NLB
- Deploy frontend

## Step 3: Verify API via CloudFront

```bash
python tools/aws/scope_shared/verify/verify_all_deploy.py --scope kube --env dev
```

All endpoints (Health, Version, Frontend, QueryStream, Analytics) should pass.

## Step 4: Run orphan removal

First, run a fresh scan to get current orphans:

```bash
PYTHONPATH=$(pwd) python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py
```

Then dry-run removal:

```bash
PYTHONPATH=$(pwd) python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py --dry-run
```

If the output looks correct (Classic ELBs and k8s-elb-* SGs), run for real:

```bash
PYTHONPATH=$(pwd) python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py
```

## Step 5: Re-verify

```bash
python tools/aws/scope_shared/verify/verify_all_deploy.py --scope kube --env dev
```

## Deploy flow change (hostname change detection)

The deploy script now detects when the LB hostname **changes** after kube_apply (e.g. when the controller creates a new NLB). In that case, it runs a second tofu apply to update CloudFront with the new hostname. Previously it skipped the second apply when a hostname was known before the first apply.
