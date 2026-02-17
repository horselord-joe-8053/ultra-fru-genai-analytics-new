# Nonkube Destroy: Error Handling Deep Dive

## Stack in Question

**`live_deploy_aws/nonkube`** — Yes. This stack contains:

| Resource group | Resources | Typical destroy order (last → first) |
|----------------|-----------|-------------------------------------|
| **Frontend** | S3 bucket policy, CloudFront distribution, OAC, S3 bucket | Policy → Distribution → OAC → Bucket |
| **ECS/ALB** | ECS service, target group, listener, ALB, security groups, cluster, log groups | Service → TG/Listener → ALB → SGs → Cluster |
| **Spark/EventBridge** | Event target, event rule, task def, IAM roles | Target → Rule → Task def → IAM |
| **Shared refs** | data.terraform_remote_state (shared_durable, shared_nondurable) | N/A |

---

## Possible Destroy Errors (by root cause)

### 1. **Async deletion (time-based — retry with wait)**

| Error substring | Resource | Cause | Resolution |
|-----------------|----------|-------|------------|
| `OriginAccessControlInUse` | OAC | CloudFront distribution still deleting (~15–40 min) | Wait 15–30 min, retry |
| `ResourceNotReady` / `exceeded wait attempts` | ECS service | Service draining takes > provider timeout | Wait, retry |
| `DependencyViolation` (ENI/security group) | Security group | ENIs from ECS tasks not yet released | Wait for ENI release (~2–5 min), retry |
| `InvalidParameterValue` (target group in use) | ALB target group | Targets still deregistering | Wait, retry |

### 2. **Dependency ordering (re-run can help)**

| Error substring | Resource | Cause | Resolution |
|-----------------|----------|-------|------------|
| `ClusterContainsContainerInstancesException` | ECS cluster | Services/tasks still present | Retry; Terraform should destroy service first on next run |
| `CannotDelete` (listener) | ALB listener | Target group still in use | Retry |

### 3. **State / data (retry usually does not help)**

| Error substring | Resource | Cause | Resolution |
|-----------------|----------|-------|------------|
| `BucketNotEmpty` | S3 bucket | Objects in bucket; no `force_destroy` | Add `force_destroy=true` to bucket, apply, then destroy; or empty bucket manually |
| `INACTIVE` (data source) | data.aws_ecs_cluster | Cluster already destroyed | Config change: make data source resilient |

### 4. **Transient / infra (retry may help)**

| Error substring | Cause | Resolution |
|-----------------|-------|------------|
| `RequestLimitExceeded` | API throttling | Wait, retry |
| `Throttling` | Rate limit | Wait, retry |
| `ServiceUnavailable` | AWS outage | Wait, retry |

### 5. **Non-retryable (stop and fix)**

| Error substring | Cause | Resolution |
|-----------------|-------|------------|
| `AccessDenied` | Credentials / permissions | Fix IAM |
| `InvalidClientTokenId` | Bad credentials | Fix credentials |
| `NoSuchBucket` / `ResourceNotFoundException` | Resource already gone | Often safe to ignore; may need `state rm` |

---

## Handling Order (in teardown logic)

Errors are **mutually exclusive per run** — Terraform fails on one resource at a time. On retry, a different error can appear. Handling order:

1. **Non-retryable** → Fail immediately, don’t retry.
2. **Retryable (async / timing)** → Wait, retry.
3. **Retryable (transient)** → Wait, retry.

So the order is: **non-retryable first** (fail fast), then **retryable** (wait + retry).

---

## Retryable Error Patterns (single regex/list)

Use these substrings to detect retryable errors:

```
OriginAccessControlInUse
ResourceNotReady
exceeded wait attempts
DependencyViolation
InvalidParameterValue.*target
ClusterContainsContainerInstancesException
CannotDelete
RequestLimitExceeded
Throttling
ServiceUnavailable
```

These are **retry-with-wait**; others are **fail-immediately**.

---

## Non-retryable Patterns (fail fast)

```
BucketNotEmpty
AccessDenied
InvalidClientTokenId
UnauthorizedOperation
```

---

## Implementation plan (without splitting stack)

### 1. Error classification

```python
RETRYABLE_PATTERNS = [
    "OriginAccessControlInUse",
    "ResourceNotReady",
    "exceeded wait attempts",
    "DependencyViolation",
    "ClusterContainsContainerInstancesException",
    "RequestLimitExceeded",
    "Throttling",
    "ServiceUnavailable",
]

NON_RETRYABLE_PATTERNS = [
    "BucketNotEmpty",
    "AccessDenied",
    "InvalidClientTokenId",
    "UnauthorizedOperation",
]
```

### 2. Retry logic

```
def destroy_with_retry(stack_dir, env, cmd, extra):
    attempt = 0
    max_attempts = 1 + TEARDOWN_OAC_MAX_RETRIES  # or TEARDOWN_MAX_RETRIES

    while attempt < max_attempts:
        result = run_with_heartbeat(cmd, ...)

        if result.returncode == 0:
            return  # success

        stderr = result.stderr or ""

        # 1. Non-retryable: fail immediately
        if any(p in stderr for p in NON_RETRYABLE_PATTERNS):
            print(stderr)
            raise ...

        # 2. Retryable: wait and retry
        if any(p in stderr for p in RETRYABLE_PATTERNS):
            attempt += 1
            if attempt >= max_attempts:
                print(stderr)
                raise ...
            print(f"Retryable error (attempt {attempt}/{max_attempts}); waiting {TEARDOWN_OAC_WAIT_SEC}s...")
            sleep_with_heartbeat(TEARDOWN_OAC_WAIT_SEC, "Waiting before retry...")
            continue

        # 3. Unknown error: fail (or optionally treat as retryable)
        print(stderr)
        raise ...
```

### 3. Config (.env)

| Variable | Purpose | Default |
|----------|---------|---------|
| `TEARDOWN_OAC_WAIT_SEC` | Wait before retry on retryable errors | `900` |
| `TEARDOWN_MAX_RETRIES` | Max retries (1 initial + N retries) | `2` |

### 4. Pre-emptive config changes (reduce failures)

| Change | Reduces | File |
|--------|---------|------|
| `force_destroy = true` on frontend S3 bucket | `BucketNotEmpty` | `infra_modules/aws/primitives/cloudfront/main.tf` |
| Resilient ECS cluster data source | `INACTIVE` on import | `live_deploy_aws/nonkube/main.tf` |

---

## Handling order summary

| Order | Check | Action |
|-------|-------|--------|
| 1 | Non-retryable pattern in stderr | Print stderr, raise, exit |
| 2 | Retryable pattern in stderr | Wait, retry (up to max) |
| 3 | Unknown error | Print stderr, raise (or treat as retryable) |

---

## Notes

- One retryable error can be followed by another on the next run; no extra ordering within retryable errors.
- Single wait (`TEARDOWN_OAC_WAIT_SEC`) is used for all retryable cases; a future enhancement could add per‑error wait times.
- Splitting the stack is not required; the retry logic applies to the full nonkube destroy.
