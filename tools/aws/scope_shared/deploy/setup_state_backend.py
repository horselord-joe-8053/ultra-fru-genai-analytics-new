"""
Set up the remote state backend for Terraform/OpenTofu.

- Creates the S3 state bucket if missing (versioning + encryption).
- Uses S3-native lockfile by default (Terraform/OpenTofu `use_lockfile=true`).
- Optionally creates a DynamoDB lock table if `TF_STATE_LOCK_TABLE` is set.

Usage:
  python tools/aws/scope_shared/deploy/setup_state_backend.py

WHY OUTSIDE TERRAFORM: Chicken-and-egg—Terraform needs a backend before `tofu init`, so this
bucket must exist first. Created via AWS CLI before any Terraform runs. Never destroyed by
teardown (even --incl-dura-all); manual deletion only when decommissioning.

Bucket: {prefix}-tf-state-{env}-{region}
State paths: {prefix}/{env}/{region}/{stack_id}.tfstate
"""
import os, subprocess
from tools.cloud_shared.env import load_dotenv, require

load_dotenv()

def sh(cmd):
    print("+"," ".join(cmd))
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def exists_s3(bucket):
    r = sh(["aws","s3api","head-bucket","--bucket",bucket])
    return r.returncode == 0

def create_s3(bucket, region):
    if region == "us-east-1":
        sh(["aws","s3api","create-bucket","--bucket",bucket])
    else:
        sh(["aws","s3api","create-bucket","--bucket",bucket,"--create-bucket-configuration",f"LocationConstraint={region}"])
    sh(["aws","s3api","put-bucket-versioning","--bucket",bucket,"--versioning-configuration","Status=Enabled"])
    sh(["aws","s3api","put-bucket-encryption","--bucket",bucket,"--server-side-encryption-configuration",
        '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
    ])

def exists_ddb(table, region):
    r = sh(["aws", "dynamodb", "describe-table", "--table-name", table, "--region", region])
    return r.returncode == 0

def create_ddb(table, region):
    sh([
        "aws", "dynamodb", "create-table",
        "--table-name", table,
        "--attribute-definitions", "AttributeName=LockID,AttributeType=S",
        "--key-schema", "AttributeName=LockID,KeyType=HASH",
        "--billing-mode", "PAY_PER_REQUEST",
        "--region", region,
    ])
    sh(["aws", "dynamodb", "wait", "table-exists", "--table-name", table, "--region", region])

def main():
    from tools.aws.scope_shared.core.backend import resolve_region, resolve_state_bucket, resolve_state_lock_table
    region = resolve_region(None)
    bucket = resolve_state_bucket(region)

    if not exists_s3(bucket):
        print("Creating state bucket:", bucket, "in", region)
        create_s3(bucket, region)
    else:
        print("State bucket exists:", bucket)

    table = resolve_state_lock_table(region)
    if table:
        if not exists_ddb(table, region):
            print("Creating lock table:", table, "in", region)
            create_ddb(table, region)
        else:
            print("Lock table exists:", table)
    else:
        print("Using S3-native lockfile (no DynamoDB lock table).")

if __name__ == "__main__":
    main()
