
"""
Bootstrap the remote state backend.

Legacy-aligned:
- Creates the S3 state bucket if missing (versioning + encryption).
- Uses S3-native lockfile by default (Terraform/OpenTofu `use_lockfile=true`).
- Optionally creates a DynamoDB lock table if `TF_STATE_LOCK_TABLE` (or `TF_LOCK_TABLE`) is set.

Usage:
  python tools/aws/common/deploy/bootstrap_state_backend.py
"""
import os, subprocess
from tools.common.env import load_dotenv, require

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

def exists_ddb(table):
    r = sh(["aws","dynamodb","describe-table","--table-name",table])
    return r.returncode == 0

def create_ddb(table):
    sh([
        "aws","dynamodb","create-table",
        "--table-name",table,
        "--attribute-definitions","AttributeName=LockID,AttributeType=S",
        "--key-schema","AttributeName=LockID,KeyType=HASH",
        "--billing-mode","PAY_PER_REQUEST"
    ])
    sh(["aws","dynamodb","wait","table-exists","--table-name",table])

def main():
    bucket = require("TF_STATE_BUCKET")
    region = os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION")

    if not exists_s3(bucket):
        print("Creating state bucket:", bucket)
        create_s3(bucket, region)
    else:
        print("State bucket exists:", bucket)

    table = (os.getenv("TF_STATE_LOCK_TABLE") or os.getenv("TF_LOCK_TABLE") or "").strip()
    if table:
        if not exists_ddb(table):
            print("Creating lock table:", table)
            create_ddb(table)
        else:
            print("Lock table exists:", table)
    else:
        print("Using S3-native lockfile (no DynamoDB lock table).")

if __name__ == "__main__":
    main()
