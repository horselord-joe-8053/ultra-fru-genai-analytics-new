# Cross-Region Teardown: CloudFront Comment Fallback Bug

**Date:** 2025-02-10

## Symptom

Teardown with `--cloud-region us-east-1` breaks CloudFront URLs in **us-east-2**:
- `https://d2faaapar85y82.cloudfront.net/`
- `https://d1wwx31d7ebvpg.cloudfront.net/`

## Root Cause

The CloudFront pre-destroy fallback uses **comment search** when tofu output fails. The comment is:

```
${var.prefix}-${var.env}-frontend-${var.suffix}
```

e.g. `fru-dev-frontend-nonkube` or `fru-dev-frontend-kube` — **no region**.

When multiple regions are deployed, both us-east-1 and us-east-2 have distributions with the same comment. `_find_distribution_id_by_comment()` returns the **first** match from the API (order undefined). If us-east-1 state is empty or tofu output fails, we can accidentally delete **us-east-2's** distribution.

## When Does Tofu Output Fail?

- us-east-1 was never deployed (state empty)
- us-east-1 was already torn down (state empty)
- State corruption or init failure
- Output missing from state

## Components Affected

| Component | Per-Region? | Affected by us-east-1 Teardown? |
|-----------|-------------|----------------------------------|
| CloudFront distribution | Yes (one per region per scope) | **Yes (BUG)** — comment fallback can delete wrong region's distribution |
| CloudFront OAC | Yes (region-scoped name) | No — we only delete `*-us-east-1-oac` |
| S3 frontend bucket | Yes (region in name) | No |
| ECR, S3 delta/artifacts | Yes (region suffix) | No |
| VPC, Aurora, durable | Yes (per-region state) | No |

## Fix (Implemented)

1. **Add region to CloudFront comment** in `infra_terraform/modules/aws/primitives/cloudfront/main.tf`:
   ```hcl
   comment = "${var.prefix}-${var.env}-frontend-${var.suffix}-${var.aws_region}"
   ```

2. **Update pre-destroy fallback** in `cloudfront_pre_destroy.py` to use the same region-scoped comment when looking up by comment.

**Note:** Existing deployments have the old comment (no region). After this fix, new deploys will get region-scoped comments. The tofu output path (primary) is unaffected; only the fallback is fixed for future consistency.
