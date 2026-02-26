#!/usr/bin/env python3
"""
One-off migration: Split Terraform state into region-specific buckets per
docs/learned/terra/TERRA_LEARNED_TOTAL.md (region-specific state).

Phases:
  1. Preparation: Get account ID, list old bucket layout
  3. Create resources: New buckets + DynamoDB lock tables per region
  4. Copy state: Copy state files from old bucket to new region buckets

Idempotent: Skips bucket/table creation if already exists.
Uses heartbeat for long-running steps and retry for transient AWS errors.

Usage:
  PYTHONPATH=. python tools/aws/standalone/temp_one_off/split_buckets_even_for_regions.py
  PYTHONPATH=. python tools/aws/standalone/temp_one_off/split_buckets_even_for_regions.py --env dev --regions us-east-1,us-east-2
"""
import argparse
import json
import os
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.cloud_shared.logging.logger import Heartbeat
from tools.cloud_shared.retry import run_with_retry, run_with_heartbeat
from tools.aws.scope_shared.core.terra_runner import get_terra_env

load_dotenv()

# Defaults from refactor doc
OLD_BUCKET = "fru-terraform-state-744139897900"
STATE_KEYS = ["aws-shared-durable", "aws-shared-nondurable", "aws-kube", "aws-nonkube"]
REGIONS = ["us-east-1", "us-east-2"]


def _aws_cmd(cmd: list[str], region: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run AWS CLI with heartbeat. Returns CompletedProcess."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    env = env or get_terra_env(region)
    return run_with_heartbeat(
        full,
        cwd=os.getcwd(),
        env=env,
        description=f"AWS {' '.join(cmd[:3])}...",
        interval_sec=15,
    )


def _aws_json(cmd: list[str], region: str | None = None) -> dict:
    """Run AWS CLI, return parsed JSON. Returns {} on failure."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    try:
        out = subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=60,
            env=get_terra_env(region),
        )
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {}


def _get_account_id() -> str:
    data = _aws_json(["sts", "get-caller-identity"])
    return data.get("Account", "")


def phase1_preparation(env: str, prefix: str) -> tuple[str, list[str]]:
    """Phase 1: Get account ID, list old bucket. Returns (account_id, list of keys)."""
    logger.step("Phase 1: Preparation")
    account_id = _get_account_id()
    if not account_id:
        logger.error("Could not get AWS account ID (check credentials)")
        sys.exit(1)
    logger.info(f"Account ID: {account_id}")

    with Heartbeat("Listing old bucket layout", interval=10):
        out = _aws_cmd(["s3", "ls", f"s3://{OLD_BUCKET}/", "--recursive"])
        if out.returncode != 0:
            logger.warning(f"Old bucket list returned {out.returncode}; may not exist yet")
            keys = []
        else:
            keys = [line.split()[-1] for line in (out.stdout or "").splitlines() if line.strip()]
            logger.info(f"Found {len(keys)} objects in {OLD_BUCKET}")

    return account_id, keys


def _bucket_exists(bucket: str) -> bool:
    out = subprocess.run(
        ["aws", "s3api", "head-bucket", "--bucket", bucket],
        capture_output=True,
        text=True,
        timeout=10,
        env=get_terra_env(),
    )
    return out.returncode == 0


def _table_exists(table: str, region: str) -> bool:
    data = _aws_json(["dynamodb", "describe-table", "--table-name", table], region=region)
    return "Table" in data


def phase3_create_resources(
    env: str,
    prefix: str,
    account_id: str,
    bucket_prefix: str,
    lock_prefix: str,
    regions: list[str],
) -> None:
    """Phase 3: Create buckets and DynamoDB lock tables per region."""
    logger.step("Phase 3: Create resources")
    for region in regions:
        bucket = f"{bucket_prefix}-{env}-{region}-{account_id}"
        table = f"{lock_prefix}-{region}"
        logger.info(f"[{region}] Bucket: {bucket}, Lock table: {table}")

        # Create bucket (idempotent)
        if _bucket_exists(bucket):
            logger.info(f"[{region}] Bucket {bucket} already exists, skipping create")
        else:
            cmd = ["s3api", "create-bucket", "--bucket", bucket]
            if region != "us-east-1":
                cmd += ["--create-bucket-configuration", f"LocationConstraint={region}"]
            out = _aws_cmd(cmd, region=region)
            if out.returncode != 0:
                if "BucketAlreadyOwnedByYou" in (out.stderr or "") or "BucketAlreadyExists" in (out.stderr or ""):
                    logger.info(f"[{region}] Bucket already exists (race), continuing")
                else:
                    logger.error(f"[{region}] Failed to create bucket: {out.stderr}")
                    sys.exit(1)
            else:
                logger.success(f"[{region}] Created bucket {bucket}")

        # Versioning
        out = _aws_cmd(
            ["s3api", "put-bucket-versioning", "--bucket", bucket, "--versioning-configuration", "Status=Enabled"],
            region=region,
        )
        if out.returncode != 0:
            logger.warning(f"[{region}] put-bucket-versioning failed: {out.stderr}")
        else:
            logger.info(f"[{region}] Versioning enabled")

        # Encryption
        enc = '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
        out = _aws_cmd(
            ["s3api", "put-bucket-encryption", "--bucket", bucket, "--server-side-encryption-configuration", enc],
            region=region,
        )
        if out.returncode != 0:
            logger.warning(f"[{region}] put-bucket-encryption failed: {out.stderr}")
        else:
            logger.info(f"[{region}] Encryption enabled")

        # DynamoDB lock table (idempotent)
        if _table_exists(table, region):
            logger.info(f"[{region}] Lock table {table} already exists, skipping create")
        else:
            out = _aws_cmd(
                [
                    "dynamodb", "create-table",
                    "--table-name", table,
                    "--attribute-definitions", "AttributeName=LockID,AttributeType=S",
                    "--key-schema", "AttributeName=LockID,KeyType=HASH",
                    "--billing-mode", "PAY_PER_REQUEST",
                ],
                region=region,
            )
            if out.returncode != 0:
                if "ResourceInUseException" in (out.stderr or ""):
                    logger.info(f"[{region}] Table already exists (race), continuing")
                else:
                    logger.error(f"[{region}] Failed to create table: {out.stderr}")
                    sys.exit(1)
            else:
                logger.success(f"[{region}] Created lock table {table}")


def phase4_copy_state(
    env: str,
    prefix: str,
    account_id: str,
    bucket_prefix: str,
    regions: list[str],
) -> None:
    """Phase 4: Copy state files from old bucket to new region buckets."""
    logger.step("Phase 4: Copy state")
    base_path = f"{prefix}/{env}"
    for region in regions:
        bucket = f"{bucket_prefix}-{env}-{region}-{account_id}"
        for key in STATE_KEYS:
            src = f"s3://{OLD_BUCKET}/{base_path}/{region}/{key}.tfstate"
            dst = f"s3://{bucket}/{base_path}/{region}/{key}.tfstate"
            with Heartbeat(f"Copy {key}.tfstate to {region}", interval=10):
                out = _aws_cmd(["s3", "cp", src, dst])
            if out.returncode != 0:
                if "404" in (out.stderr or "") or "NoSuchKey" in (out.stderr or ""):
                    logger.warning(f"[{region}] {key}.tfstate not found in old bucket, skipping")
                else:
                    logger.error(f"[{region}] Copy failed for {key}: {out.stderr}")
                    sys.exit(1)
            else:
                logger.success(f"[{region}] Copied {key}.tfstate")


def main():
    ap = argparse.ArgumentParser(description="Split Terraform state into region-specific buckets")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--prefix", default=os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru"))
    ap.add_argument("--regions", default=",".join(REGIONS), help="Comma-separated regions")
    ap.add_argument("--skip-phase1", action="store_true", help="Skip Phase 1 (list old bucket)")
    ap.add_argument("--skip-phase3", action="store_true", help="Skip Phase 3 (create resources)")
    ap.add_argument("--skip-phase4", action="store_true", help="Skip Phase 4 (copy state)")
    args = ap.parse_args()

    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    proj = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    comp = os.getenv("TF_STATE_BUCKET_COMPONENT", "tf-state")
    bucket_prefix = os.getenv("TF_STATE_BUCKET_PREFIX") or f"{proj}-{comp}"
    lock_comp = os.getenv("TF_LOCK_TABLE_COMPONENT", "tf-locks-tbl")
    lock_prefix = os.getenv("TF_LOCK_TABLE_PREFIX") or f"{proj}-{lock_comp}"

    logger.step(f"Split buckets for regions: {regions} (env={args.env}, prefix={args.prefix})")
    start = time.time()

    account_id = _get_account_id()
    if not account_id:
        logger.error("Could not get AWS account ID")
        sys.exit(1)

    if not args.skip_phase1:
        phase1_preparation(args.env, args.prefix)
    else:
        logger.info("Skipping Phase 1")

    if not args.skip_phase3:
        phase3_create_resources(
            args.env, args.prefix, account_id, bucket_prefix, lock_prefix, regions
        )
    else:
        logger.info("Skipping Phase 3")

    if not args.skip_phase4:
        phase4_copy_state(args.env, args.prefix, account_id, bucket_prefix, regions)
    else:
        logger.info("Skipping Phase 4")

    elapsed = int(time.time() - start)
    logger.success(f"Split buckets completed in {elapsed}s")


if __name__ == "__main__":
    main()
