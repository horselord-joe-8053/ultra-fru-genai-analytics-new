# Bedrock: "Credentials were refreshed, but the refreshed credentials are still expired"

## Root cause

Nonkube ECS uses the **task role** (`fru-dev-ecs-task-<region>`, e.g. `fru-dev-ecs-task-us-east-1`) for Bedrock. There are no explicit `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` from Secrets Manager—unlike kube, which injects them via the `aws-credentials` K8s secret.

This error usually means:

1. **Stale task role credentials** – ECS metadata returns credentials that boto3 tries to refresh, but the refreshed set is also expired (e.g. metadata endpoint returning old values).
2. **`AWS_CREDENTIAL_EXPIRATION` env var** – If set with an expired timestamp, boto3 treats credentials as expired even after refresh.
3. **IAM role issues** – Role was deleted/recreated, or sessions need revoking.
4. **Clock skew** – Container clock out of sync (less common on Fargate).

---

## How to check

### 1. Verify task role exists and has Bedrock permissions

```bash
CLUSTER="fru-dev-ecs"   # or from tofu output ecs_cluster_name
SERVICE="fru-dev-api-svc"
REGION="us-east-1"

# Get task definition and task role ARN
aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION \
  --query 'services[0].taskDefinition' --output text

aws ecs describe-task-definition --task-definition <task-def-arn> --region $REGION \
  --query 'taskDefinition.taskRoleArn' --output text

# Check role has bedrock policy
ROLE_NAME="fru-dev-ecs-task"
aws iam list-attached-role-policies --role-name $ROLE_NAME --region $REGION
aws iam list-role-policies --role-name $ROLE_NAME --region $REGION
```

### 2. Inspect running task env (no AWS_CREDENTIAL_EXPIRATION)

```bash
# Get a running task ARN
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --region $REGION \
  --query 'taskArns[0]' --output text)

# Task env is in the task definition; check that no stale AWS_CREDENTIAL_EXPIRATION is passed
# (nonkube main.tf does NOT inject it; only kube uses explicit credentials)
```

### 3. Check CloudWatch logs for credential-related errors

```bash
aws logs filter-log-events \
  --log-group-name "/fru/dev/ecs-api" \
  --filter-pattern "credential" \
  --region $REGION \
  --start-time $(date -v-1H +%s000) \
  --limit 20
```

---

## Fixes (in order of likelihood)

### Fix 1: Force new ECS deployment (most common)

Starts new tasks with fresh credentials from the metadata endpoint.

```bash
CLUSTER="fru-dev-ecs"
SERVICE="fru-dev-api-svc"
REGION="us-east-1"

aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --force-new-deployment \
  --region $REGION
```

Wait 2–3 minutes for new tasks to become healthy, then retry `/query/stream`.

---

### Fix 2: Revoke IAM role sessions

If Fix 1 does not help, the task role may have stale sessions.

1. AWS Console → IAM → Roles → `fru-dev-ecs-task-<region>` (e.g. `fru-dev-ecs-task-us-east-1`)
2. **Revoke sessions** tab → **Revoke active sessions**

Then run Fix 1 again to start new tasks.

---

### Fix 3: Re-apply Terraform (refresh IAM)

If the task role or its policies were changed, re-apply the nonkube stack:

```bash
cd /path/to/fru-genai-analytics-new
CLOUD_REGION=us-east-1 python orchestrator.py deploy --scope nonkube --env dev --cloud-region us-east-1
```

Or tofu directly on the nonkube stack. This refreshes the task role and its Bedrock policy.

---

### Fix 4: Use explicit credentials (workaround)

If the task role path keeps failing, you can switch nonkube to explicit credentials (like kube):

1. Add an `aws-credentials` secret in Secrets Manager (or reuse a shared secret).
2. Extend the ECS module to accept `secret_arns` for `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
3. Ensure `ensure_secrets` (or a similar tool) populates that secret from `AWS_ADMIN_*` or `AWS_BEDROCK_*` in `.env`.

This is a larger change; Fix 1–3 usually resolve the issue.

---

## Quick one-liner

```bash
aws ecs update-service --cluster fru-dev-ecs --service fru-dev-api-svc --force-new-deployment --region us-east-1

# Note: IAM roles are now region-suffixed (fru-dev-ecs-task-us-east-1) to avoid cross-region teardown conflicts.
```

Then wait ~2 minutes and retry verify or `/query/stream`.
