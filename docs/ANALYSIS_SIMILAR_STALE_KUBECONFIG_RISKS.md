# Analysis: Similar Stale Kubectl Context / Wrong-Region Risks

**Date:** 2026-02-24  
**Context:** After fixing deploy_kube.py `_try_get_lb_hostname` to reject wrong-region NLB hostnames, audit for similar patterns.

---

## Pattern: kubectl returns data from current context (not deploy region)

**Root cause:** kubectl uses `~/.kube/config`; the current context points at whichever cluster was last configured. If the user deployed us-east-2, then deploys us-east-1, kubectl may still point at us-east-2. Any code that runs kubectl without first running `eks_kubeconfig` for the deploy region can get wrong-region data.

**eks_kubeconfig.py** uses `resolve_region(None)` → `CLOUD_REGION`. So callers must set `CLOUD_REGION` (or pass region to a subprocess that sets it) before running eks_kubeconfig.

---

## Findings

### 1. deploy_kube.py `_try_get_lb_hostname` — FIXED

- **Risk:** Called before first tofu apply; eks_kubeconfig runs later. kubectl could return wrong-region NLB.
- **Impact:** CloudFront wired to wrong-region NLB → broken after that region is torn down.
- **Fix:** Region validation added: reject hostname if it doesn't contain deploy region.

---

### 2. verify_all_deploy.py — kubectl fallback (lines 357–378)

- **Location:** Fallback when `cf_domain` is empty (CloudFront not in outputs yet).
- **Risk:** Runs `kubectl get svc fru-api-svc` **without** running eks_kubeconfig first. No region validation on returned hostname.
- **Impact:** Could verify against wrong region's backend. Pass when it shouldn't, or fail when it shouldn't.
- **Fix:** Run `eks_kubeconfig` with deploy region before kubectl; validate `lb_host` contains region (defense in depth).

---

### 3. deploy.py `_print_success_url` (lines 66–80)

- **Location:** Fallback when CloudFront domain not in outputs; prints success URL.
- **Risk:** Runs `kubectl get svc fru-api-svc` without eks_kubeconfig. No region validation.
- **Impact:** Could print wrong URL (e.g. us-east-2 NLB when deploying us-east-1). Display only—does not wire infra.
- **Fix:** Run eks_kubeconfig before kubectl, or reuse `_try_get_lb_hostname` from deploy_kube with region validation.

---

### 4. bootstrap_helpers — SAFE

- `check_k8s_bootstrap_job_succeeded`: Runs eks_kubeconfig first. Uses CLOUD_REGION from env (set by kube_apply).
- `wait_for_fru_api_ready`: Runs eks_kubeconfig first; passes region in env.
- `k8s_rollout_restart_api`: Runs eks_kubeconfig first; passes region in env.
- `k8s_remove_bootstrap_and_scheduler`: Runs eks_kubeconfig first. Teardown sets CLOUD_REGION before running.

---

### 5. teardown_orphan_cleanup — SAFE

- Uses AWS CLI with explicit `--region`. No kubectl. Region from `resolve_region(None)`.

---

### 6. AWS CLI calls without --region

- **doctor.py** `aws sts get-caller-identity`: No region needed (global). OK.
- **backend.py** `aws s3api get-bucket-location`: S3 global endpoint; region not required for this call. Low risk.
- **teardown.py**, **verify_all_deploy.py** AWS calls: All pass `--region` explicitly. OK.

---

## Summary

| File                    | Pattern                    | Risk | Status   |
|-------------------------|----------------------------|------|----------|
| deploy_kube.py           | _try_get_lb_hostname       | High | Fixed    |
| verify_all_deploy.py     | kubectl fallback           | Medium | Needs fix |
| deploy.py                | _print_success_url kubectl | Low  | Needs fix |

---

## Recommended Fixes

1. **verify_all_deploy.py:** Before kubectl fallback, run `eks_kubeconfig` with deploy region. Add region validation on `lb_host` (reject if hostname doesn't contain region).
2. **deploy.py:** Before kubectl in `_print_success_url`, run `eks_kubeconfig` with region, or call `deploy_kube._try_get_lb_hostname(env, region)` (shared logic, already has validation).
