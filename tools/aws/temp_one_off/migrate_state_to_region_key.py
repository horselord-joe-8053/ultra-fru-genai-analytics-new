"""
One-time migration of Terraform state from legacy key to region-scoped key.

Usage:
  python tools/aws/temp_one_off/migrate_state_to_region_key.py --env dev --region us-east-1 --dry-run
  python tools/aws/temp_one_off/migrate_state_to_region_key.py --env dev --region us-east-1 --execute

Migrates state from:
  {prefix}/{env}/{stack_id}.tfstate
to:
  {prefix}/{env}/{region}/{stack_id}.tfstate

Stacks: shared/durable, shared/nondurable, kube, nonkube
"""
import argparse
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv, require
from tools.aws.common.core.backend import backend_config, stack_id_from_dir
from tools.cloud_shared.logging import logger

load_dotenv()

STACK_DIRS = [
    "live_deploy_aws/scope_shared/durable",
    "live_deploy_aws/scope_shared/nondurable",
    "live_deploy_aws/kube",
    "live_deploy_aws/nonkube",
]


def get_s3_key(stack_dir: str, env: str, region: str | None) -> str:
    """Return S3 key for a stack (legacy or region-scoped)."""
    cfg = backend_config(stack_dir, env, region)
    for c in cfg:
        if c.startswith("key="):
            return c.split("=", 1)[1]
    raise ValueError(f"No key in backend config for {stack_dir}")


def s3_object_exists(bucket: str, key: str, region: str) -> bool:
    """Check if S3 object exists."""
    try:
        r = subprocess.run(
            ["aws", "s3api", "head-object", "--bucket", bucket, "--key", key, "--region", region],
            capture_output=True,
            check=False,
            timeout=10,
        )
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def s3_copy(bucket: str, old_key: str, new_key: str, region: str) -> None:
    """Copy S3 object (same bucket)."""
    src = f"s3://{bucket}/{old_key}"
    dst = f"s3://{bucket}/{new_key}"
    logger.info(f"[COPY] {src} -> {dst}")
    subprocess.run(
        ["aws", "s3", "cp", src, dst, "--region", region],
        check=True,
        timeout=60,
    )


def main():
    ap = argparse.ArgumentParser(description="Migrate Terraform state to region-scoped S3 keys")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", required=True, help="Target AWS region for new keys")
    ap.add_argument("--dry-run", action="store_true", help="List objects that would be copied")
    ap.add_argument("--execute", action="store_true", help="Perform the copy")
    args = ap.parse_args()

    if not args.dry_run and not args.execute:
        logger.error("Specify --dry-run or --execute")
        sys.exit(1)

    region = args.region.strip()
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region

    bucket = require("TF_STATE_BUCKET")
    prefix = os.getenv("TF_STATE_PREFIX", require("FRU_PREFIX"))

    logger.step(f"State migration: env={args.env}, region={region}, bucket={bucket}")

    to_copy = []
    for stack_dir in STACK_DIRS:
        stack_id = stack_id_from_dir(stack_dir)
        old_key = get_s3_key(stack_dir, args.env, None)
        new_key = get_s3_key(stack_dir, args.env, region)

        if s3_object_exists(bucket, old_key, region):
            to_copy.append((old_key, new_key, stack_id))
        else:
            logger.info(f"[SKIP] {stack_id}: no object at {old_key}")

    if not to_copy:
        logger.info("Nothing to migrate.")
        sys.exit(0)

    logger.info(f"Would migrate {len(to_copy)} state file(s):")
    for old_key, new_key, stack_id in to_copy:
        logger.info(f"  {stack_id}: {old_key} -> {new_key}")

    if args.dry_run:
        logger.success("Dry run complete. Run with --execute to perform migration.")
        sys.exit(0)

    for old_key, new_key, stack_id in to_copy:
        try:
            s3_copy(bucket, old_key, new_key, region)
            logger.success(f"[OK] {stack_id}")
        except subprocess.CalledProcessError as e:
            logger.error(f"[FAIL] {stack_id}: {e}")
            sys.exit(1)

    logger.success("Migration complete. Deploy/teardown must use --region " + region)


if __name__ == "__main__":
    main()
