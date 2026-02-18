# CloudFront Teardown Analysis

## Current State (from AWS + Terraform)

| Resource | AWS | Terraform State |
|----------|-----|-----------------|
| Distribution E3GQGDB2AU79HU (fru-dev-frontend-nonkube) | **Exists, Enabled=true, Status=Deployed** | **Not in state** |
| OAC E42GNKTR7R2CW (fru-dev-frontend-nonkube-oac) | Exists | **In state** |
| Other (S3, ALB, etc.) | - | Not in state |

## Root Cause

**The distribution is orphaned**: it exists in AWS but was removed from Terraform state during a previous teardown run. Terraform destroy removes resources from state as it destroys them. When destroy failed on the OAC (because distribution was still deleting), the state was left with only the OAC. The distribution had already been removed from state.

**Why the distribution was never deleted in AWS**: Two possibilities:
1. **Terraform never sent the delete** – The destroy order may have hit OAC before distribution in some edge case.
2. **Deploy was run after failed teardown** – Deploy recreated the distribution. The OAC stayed in state from the failed teardown.

Either way, the distribution is currently **Enabled** and **Deployed** – it was never disabled or deleted.

## Why OAC Can't Be Deleted

AWS CloudFront: **you cannot delete an OAC while it is still referenced by a distribution**. The distribution must be deleted first. Distribution deletion is async (disable → propagate ~15–30 min → delete).

## Fix: Manual delete via AWS CLI, then teardown

Import fails because the nonkube stack has data sources (e.g. ECS cluster) that are INACTIVE after partial teardown. Use AWS CLI to delete the distribution manually, then run teardown to remove the OAC from state:

```bash
# 1. Disable the distribution (required before delete)
DIST_ID=E3GQGDB2AU79HU
ETAG=$(aws cloudfront get-distribution-config --id $DIST_ID --query 'ETag' --output text)
aws cloudfront get-distribution-config --id $DIST_ID --query 'DistributionConfig' --output json | \
  jq '.Enabled = false' > /tmp/cfg.json
aws cloudfront update-distribution --id $DIST_ID --if-match $ETAG --distribution-config file:///tmp/cfg.json

# 2. Wait ~15–30 min for propagation (check status until Deployed)
aws cloudfront get-distribution --id $DIST_ID --query 'Distribution.Status'

# 3. Delete the distribution
ETAG=$(aws cloudfront get-distribution-config --id $DIST_ID --query 'ETag' --output text)
aws cloudfront delete-distribution --id $DIST_ID --if-match $ETAG

# 4. Run teardown to remove OAC from state
PYTHONPATH=. python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
```

## Workaround: Remove OAC from state to unblock teardown

If OAC delete keeps failing after retries (OriginAccessControlInUse), remove it from state so teardown can proceed. The OAC will remain in AWS until CloudFront releases it (or delete manually later):

```bash
cd infra_terraform/live_deploy/aws/nonkube
# Init with backend (use same backend-config as teardown)
tofu init -lock=false -upgrade -reconfigure -backend-config bucket=... -backend-config key=fru/dev/us-east-1/aws-nonkube.tfstate ...
tofu state rm 'module.frontend.aws_cloudfront_origin_access_control.frontend'
# Then run teardown again
PYTHONPATH=. python tools/aws/teardown.py --scope all --env dev --non-interactive
```

## Deploy: Import OAC when it exists in AWS but not in state

If OAC was removed from state (per workaround above) but the CloudFront distribution still exists and uses it, a subsequent deploy will fail with `OriginAccessControlAlreadyExists`. Import the existing OAC into state:

```bash
# OAC ID: look up via AWS Console or: aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='fru-dev-frontend-nonkube-oac'].Id" --output text
cd infra_terraform/live_deploy/aws/nonkube
# Set TF vars (deploy uses get_base_vars)
PYTHONPATH=. python -c "
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
import subprocess, os
get_base_vars('dev', 'us-east-1')
subprocess.run(['tofu', 'import', '-lock=false', 'module.frontend.aws_cloudfront_origin_access_control.frontend', 'E268PVJGN2YYRR'],
  cwd='infra_terraform/live_deploy/aws/nonkube', env=os.environ, check=True)
"
# Then re-run deploy
PYTHONPATH=. python tools/aws/deploy.py --scope all --env dev
```
