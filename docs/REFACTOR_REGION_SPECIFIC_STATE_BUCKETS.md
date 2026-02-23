# Refactor: Region-Specific Terraform State Buckets + Lock Tables

Single prefix + runtime composition. No overrides.

---

## 1. Naming

| Resource | Formula | Example (dev, us-east-2) |
|----------|---------|---------------------------|
| **State bucket** | `{TF_STATE_BUCKET_PREFIX}-{env}-{region}-{account_id}` | `fru-tf-state-dev-us-east-2-744139897900` |
| **Lock table** | `{TF_LOCK_TABLE_PREFIX}-{region}` | `fru-tf-locks-tbl-us-east-2` |

**Env vars (required):**
```bash
TF_STATE_BUCKET_PREFIX=fru-tf-state
TF_LOCK_TABLE_PREFIX=fru-tf-locks-tbl
```

**Inputs:** `env` from `FRU_ENV`, `region` from `CLOUD_REGION`, `account_id` from `aws sts get-caller-identity` or `AWS_ACCOUNT_ID`.

---

## 2. DynamoDB Lock Table (Conceptual)

| Attribute | Purpose |
|-----------|---------|
| **LockID** (partition key) | State file identifier (e.g. `bucket/key`). One lock per state file. |
| (metadata) | Who, when, what operation (plan/apply/destroy). |

Terraform writes a lock before plan/apply/destroy and deletes it when done. Per-region tables → full isolation.

---

## 3. Code Changes

| File | Change |
|------|--------|
| **backend.py** | `resolve_state_bucket(region)` → `{TF_STATE_BUCKET_PREFIX}-{env}-{region}-{account_id}`. `resolve_state_lock_table(region)` → `{TF_LOCK_TABLE_PREFIX}-{region}`. Remove `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, and per-region overrides. Add `_get_account_id()` helper. |
| **bootstrap_state_backend.py** | Pass `--region` to `aws dynamodb create-table`. |
| **doctor.py** | Require `TF_STATE_BUCKET_PREFIX` and `TF_LOCK_TABLE_PREFIX`. |
| **scan/config.py** | Add `name.startswith(f"{prefix}-tf-state")` to S3 `is_project_resource`; add `"tf-state" in name` to S3 `classify_project_category` for shared-durable. |
| **.env.example** | Replace `TF_STATE_BUCKET` / `TF_LOCK_TABLE` with prefix vars. |

---

## 4. Migration Steps

### Phase 1: Preparation

```bash
ACCOUNT=$(AWS_PROFILE=admin aws sts get-caller-identity --query Account --output text)
AWS_PROFILE=admin aws s3 ls s3://fru-terraform-state-744139897900/ --recursive  # confirm layout
```

### Phase 2: Implement Code

Update `backend.py`, `bootstrap_state_backend.py`, `doctor.py`, `scan/config.py`, `.env.example` per §3.

### Phase 3: Create Resources

```bash
export TF_STATE_BUCKET_PREFIX=fru-tf-state TF_LOCK_TABLE_PREFIX=fru-tf-locks-tbl FRU_ENV=dev
ACCOUNT=$(AWS_PROFILE=admin aws sts get-caller-identity --query Account --output text)

for REGION in us-east-1 us-east-2; do
  BUCKET="${TF_STATE_BUCKET_PREFIX}-${FRU_ENV}-${REGION}-${ACCOUNT}"
  TABLE="${TF_LOCK_TABLE_PREFIX}-${REGION}"
  AWS_PROFILE=admin aws s3api create-bucket --bucket "$BUCKET" \
    $([ "$REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$REGION")
  AWS_PROFILE=admin aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
  AWS_PROFILE=admin aws s3api put-bucket-encryption --bucket "$BUCKET" \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  AWS_PROFILE=admin aws dynamodb create-table --region "$REGION" --table-name "$TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST
done
```

### Phase 4: Copy State

```bash
export TF_STATE_BUCKET_PREFIX=fru-tf-state FRU_ENV=dev
ACCOUNT=$(AWS_PROFILE=admin aws sts get-caller-identity --query Account --output text)
OLD="fru-terraform-state-744139897900"
for REGION in us-east-1 us-east-2; do
  BUCKET="${TF_STATE_BUCKET_PREFIX}-${FRU_ENV}-${REGION}-${ACCOUNT}"
  for key in aws-shared-durable aws-shared-nondurable aws-kube aws-nonkube; do
    AWS_PROFILE=admin aws s3 cp "s3://${OLD}/fru/dev/${REGION}/${key}.tfstate" \
      "s3://${BUCKET}/fru/dev/${REGION}/${key}.tfstate"
  done
done
```

### Phase 5: Deploy

```bash
# .env: TF_STATE_BUCKET_PREFIX=fru-tf-state, TF_LOCK_TABLE_PREFIX=fru-tf-locks-tbl
# Remove: TF_STATE_BUCKET, TF_LOCK_TABLE

CLOUD_REGION=us-east-2 PYTHONPATH=. python tools/aws/deploy.py --scope all --env dev --region us-east-2
CLOUD_REGION=us-east-1 PYTHONPATH=. python tools/aws/deploy.py --scope all --env dev --region us-east-1  # if needed
```

### Phase 6: Verify

```bash
cd infra_terraform/live_deploy/aws/scope_shared/durable
CLOUD_REGION=us-east-2 tofu output -json

PYTHONPATH=. python tools/aws/standalone/temp_one_off/resources_scan/scan_aws_remaining.py --cloud-regions us-east-1,us-east-2
```

### Phase 7: Decommission (Later)

```bash
AWS_PROFILE=admin aws s3 rm s3://fru-terraform-state-744139897900/fru/dev/ --recursive
```

---

## 5. Summary

| Item | Value |
|------|-------|
| Bucket | `{TF_STATE_BUCKET_PREFIX}-{env}-{region}-{account_id}` |
| Lock table | `{TF_LOCK_TABLE_PREFIX}-{region}` |
| Code | `backend.py`, `bootstrap_state_backend.py`, `doctor.py`, `scan/config.py` |
| Migration | Create → copy state → update .env → deploy |
