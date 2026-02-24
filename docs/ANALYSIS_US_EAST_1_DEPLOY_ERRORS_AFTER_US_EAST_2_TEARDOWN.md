# Analysis: us-east-1 Deploy Errors After us-east-2 Teardown

**Date:** 2026-02-24  
**Context:** Deploy us-east-1 succeeded; teardown us-east-2 succeeded; runtime errors observed on us-east-1 frontends.

---

## 1. Timeline

| Time | Event |
|------|-------|
| ~02:12 | Deploy us-east-1 started |
| ~02:29 | Deploy log: "NLB hostname known before apply: **af1e4b87e48fa4ab9ad8efb4b80d0e37-729457382.us-east-2.elb.amazonaws.com**" |
| ~02:53 | Deploy us-east-1 completed; verify passed |
| ~03:20 | Teardown us-east-2 completed (NLB destroyed) |
| After 03:20 | Kube frontend (d2zdlk0age3gcc.cloudfront.net) broken |

---

## 2. Root Cause: Kube CloudFront Pointing to Wrong-Region LB

(Current: Classic ELB. With annotation: NLB. See [KUBE_LOAD_BALANCER_CLARIFICATION.md](KUBE_LOAD_BALANCER_CLARIFICATION.md).)

### 2.1 What Happened

1. **`deploy_kube.py`** calls `_try_get_lb_hostname(env, region)` **before** the first tofu apply.
2. At that moment, **kubectl context** is whatever was last configured (e.g. from a previous us-east-2 deploy).
3. **`eks_kubeconfig.py`** (which sets context to the correct region) is only run **later** during `kube_apply`—after the tofu apply.
4. So `kubectl get svc fru-api-svc` returned the NLB from the **us-east-2** cluster.
5. The deploy passed `ingress_hostname=af1e4b87e48fa4ab9ad8efb4b80d0e37-729457382.us-east-2.elb.amazonaws.com` to the **us-east-1** kube stack.
6. CloudFront for us-east-1 kube was wired to the **us-east-2** NLB.
7. When us-east-2 was torn down, that NLB was destroyed.
8. **Result:** Kube CloudFront (d2zdlk0age3gcc.cloudfront.net) now forwards `/analytics`, `/query/stream`, etc. to a **dead origin** → "Backend API not reachable", "undefined is not valid JSON".

### 2.2 Why Verify Passed

Verify ran at **02:54**, before the us-east-2 teardown (03:20). The us-east-2 NLB was still alive. Verify hit CloudFront → origin (us-east-2 NLB) → 200 OK. So verify passed. **Verify cannot detect cross-region misconfiguration**—it only checks that endpoints return 200.

---

## 3. Nonkube Issues (Likely Unrelated to Teardown)

### 3.1 Bedrock: "Credentials were refreshed, but the refreshed credentials are still expired"

- **Cause:** ECS task role or explicit credentials (from Secrets Manager) used for Bedrock. This error typically indicates:
  - IAM credentials (access key) have been rotated/revoked but the app still has old values.
  - Session token expired (rare for task roles).
  - Clock skew or SDK refresh bug.
- **Relation to teardown:** Unlikely. Nonkube ECS is in us-east-1; teardown was us-east-2.
- **Action:** Verify `AWS_ADMIN_*` or `AWS_BEDROCK_*` in `.env` are current; re-run `ensure_secrets.py` and redeploy if credentials were rotated.

### 3.2 Analytics "Updated 9 hours ago"

- **Cause:** Delta table or analytics API returns last-updated timestamp. Possible reasons:
  - EventBridge Spark schedule (e.g. every 180s) may not have run yet.
  - Stale data from a previous run.
  - Frontend caching.
- **Relation to teardown:** Unlikely. Each region has its own delta bucket (`fru-dev-delta-internal-us-east-1`).

---

## 4. Why Verify Didn't Catch These

| Check | What verify does | Why it passed |
|-------|------------------|---------------|
| /health, /version, /analytics, /query/stream | HTTP GET, expect 200 + content checks | At verify time (02:54), us-east-2 NLB was still up; CloudFront → origin returned 200 |
| Retriable 502/503 | Poll until timeout | No 502/503 at verify time |
| Cross-region validation | **None** | Verify does not validate that CloudFront origin is in the deploy region |

**Gap:** Verify assumes CloudFront origin is correct. It does not validate origin hostname region.

---

## 5. Refactor Plan

### 5.1 Fix: Reject Wrong-Region NLB in `_try_get_lb_hostname` (High Priority)

**File:** `tools/aws/kube/deploy_kube.py`

**Change:** After `kubectl` returns a hostname, validate that it belongs to the deploy region. NLB hostnames look like `xxx.us-east-2.elb.amazonaws.com`. If the hostname contains a different region (e.g. `us-east-2` when deploying `us-east-1`), return `""` so we treat it as "not found" and run the second apply with the correct hostname from poll.

```python
def _try_get_lb_hostname(env: str, region: str) -> str:
    hostname = ...  # existing kubectl logic
    if not hostname:
        return ""
    # Reject hostname from a different region (kubectl context may be stale)
    if f".{region}." not in hostname and f"{region}.elb.amazonaws.com" not in hostname:
        return ""
    return hostname
```

### 5.2 Fix: Run `eks_kubeconfig` Before `_try_get_lb_hostname` When Cluster Exists (Medium)

**Option:** Before calling `_try_get_lb_hostname`, run `eks_kubeconfig` for the deploy region. But on a **fresh** deploy, the us-east-1 EKS cluster does not exist yet—it is created during the first apply. So we cannot update kubeconfig for us-east-1 before the first apply.

**Conclusion:** We must rely on region validation of the hostname. If the cluster exists (re-deploy), `eks_kubeconfig` would have been run in a previous deploy; the context might still be wrong if the user switched regions. Region validation is the robust fix.

### 5.3 Verify Enhancement: Origin Region Check (Low)

**File:** `tools/aws/scope_shared/verify/verify_all_deploy.py`

**Change:** After getting tofu outputs, optionally validate that kube CloudFront's API origin (if present) is in the deploy region. This would require parsing CloudFront distribution config—more complex. The deploy fix (5.1) is sufficient to prevent the bug.

### 5.4 Bedrock Credentials (Separate)

- Re-run `ensure_secrets.py --env dev` if credentials were rotated.
- Consider using IRSA (IAM Roles for Service Accounts) for EKS instead of static credentials to avoid expiration issues.

---

## 6. State Corruption: module.ecs in Kube State

During redeploy, a second error appeared: the **kube** state contained `module.ecs` resources (ALB, security group rule). The kube stack does NOT have an ECS module—that belongs to nonkube. This caused:

```
Error: reading ELBv2 Load Balancer (arn:...us-east-2...): not a valid load balancer ARN
```

**Fix:** Remove stale `module.ecs` from kube state before apply:

```bash
PYTHONPATH=. python tools/aws/standalone/temp_one_off/fix_kube_state_remove_stale_ecs.py --region us-east-1
```

If resources are already gone from state (e.g. after a prior fix), the script will report "Skip (not in state)".

---

## 7. Immediate Remediation for us-east-1

**Without full redeploy:**

1. Get the **us-east-1** kube NLB hostname:
   ```bash
   CLOUD_REGION=us-east-1 python tools/aws/kube/eks_kubeconfig.py --env dev
   kubectl get svc fru-api-svc -n fru-kube -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
   ```
2. Re-apply kube stack with correct hostname:
   ```bash
   cd infra_terraform/live_deploy/aws/kube
   tofu apply -var="ingress_hostname=<us-east-1-NLB-hostname>" -auto-approve
   ```
3. Invalidate CloudFront for the kube distribution.

**With redeploy:** Apply fix 5.1, then run `orchestrator deploy --scope all --cloud-region us-east-1`. The second apply will use the correct us-east-1 NLB.
