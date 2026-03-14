#!/usr/bin/env python3
"""
Restore corrupted durable Terraform state from S3 version history.

When durable state was overwritten with nonkube state, this script restores
the previous version from S3 (if versioning is enabled).

Usage:
  python tools/aws/standalone/restore_durable_state.py --env dev --region us-east-2
  python tools/aws/standalone/restore_durable_state.py --env dev --region us-east-2 --force-rebuild
  python tools/aws/standalone/restore_durable_state.py --env dev --region us-east-2 --dry-run

Options:
  --dry-run        List versions only, do not restore
  --force-rebuild  If no version history, remove corrupted state (requires manual re-import)
  --refresh        After restore, run tofu refresh on durable and nonkube to sync state with AWS
"""
import argparse
import json
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.backend import (
    resolve_bucket_region,
    resolve_region,
    resolve_state_bucket,
    stack_id_from_dir,
)

load_dotenv()

DURABLE_STACK = "infra_terraform/live_deploy/aws/scope_shared/durable"


def get_state_key(env: str, region: str) -> str:
    """Build durable state key matching backend_config."""
    prefix = os.getenv("TF_STATE_PREFIX") or os.getenv("PROJ_PREFIX", "").strip() or "fru"
    stack_id = stack_id_from_dir(DURABLE_STACK, "aws")
    return f"{prefix}/{env}/{region}/{stack_id}.tfstate"


def list_object_versions(bucket: str, key: str, region: str) -> list[dict]:
    """List S3 object versions. Returns list of version dicts (VersionId, LastModified)."""
    cmd = [
        "aws", "s3api", "list-object-versions",
        "--bucket", bucket,
        "--prefix", key,
        "--region", region,
        "--output", "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        logger.error(f"list-object-versions failed: {result.stderr}")
        return []

    data = json.loads(result.stdout)
    versions = data.get("Versions", [])
    # Filter exact key match (prefix can return multiple)
    return [v for v in versions if v.get("Key") == key]


def copy_object_version(bucket: str, key: str, version_id: str, region: str) -> bool:
    """Overwrite current object with a specific version."""
    copy_source = f"{bucket}/{key}?versionId={version_id}"
    cmd = [
        "aws", "s3api", "copy-object",
        "--bucket", bucket,
        "--copy-source", copy_source,
        "--key", key,
        "--region", region,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        logger.error(f"copy-object failed: {result.stderr}")
        return False
    return True


def delete_object(bucket: str, key: str, region: str) -> bool:
    """Delete the state object (for force-rebuild when no version history)."""
    cmd = [
        "aws", "s3api", "delete-object",
        "--bucket", bucket,
        "--key", key,
        "--region", region,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        logger.error(f"delete-object failed: {result.stderr}")
        return False
    return True


def verify_durable_outputs(env: str, region: str) -> bool:
    """Run tofu output on durable to verify state is correct."""
    from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json

    try:
        out = tofu_output_json(DURABLE_STACK, env, region)
        vpc = out.get("vpc_id", {}).get("value")
        subnets = out.get("private_subnet_ids", {}).get("value", [])
        aurora = out.get("aurora_endpoint", {}).get("value")
        if vpc and subnets and aurora:
            logger.success("Durable outputs verified: vpc_id, private_subnet_ids, aurora_endpoint present")
            return True
        ecs = out.get("ecs_cluster_name", {}).get("value")
        if ecs:
            logger.error("State still corrupted: ecs_cluster_name present (nonkube output)")
            return False
        logger.warning("Durable outputs incomplete; may need further recovery")
        return False
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Restore durable state from S3 version history")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--dry-run", action="store_true", help="List versions only, do not restore")
    ap.add_argument(
        "--force-rebuild",
        action="store_true",
        help="If no version history, remove corrupted state (requires manual re-import)",
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="After restore, run tofu refresh on durable and nonkube to sync state with AWS",
    )
    args = ap.parse_args()

    region = args.region or resolve_region(None)
    os.environ["CLOUD_REGION"] = region

    bucket = resolve_state_bucket(region)
    key = get_state_key(args.env, region)
    bucket_region = resolve_bucket_region(bucket)

    logger.step(f"Restoring durable state: s3://{bucket}/{key}")

    versions = list_object_versions(bucket, key, bucket_region)
    if not versions:
        logger.warning("No versions found. S3 versioning may be disabled.")
        if args.force_rebuild:
            logger.step("Removing corrupted state (--force-rebuild)")
            if delete_object(bucket, key, bucket_region):
                logger.success("Corrupted state removed.")
                logger.info(
                    "Next: run tofu apply for durable. You will need to import existing "
                    "resources (VPC, subnets, Aurora) if they already exist. See docs."
                )
            sys.exit(0)
        logger.error("Cannot restore. Enable S3 versioning or use --force-rebuild (requires re-import).")
        sys.exit(1)

    # Sort by LastModified descending (newest first)
    versions.sort(key=lambda v: v.get("LastModified", ""), reverse=True)
    current = versions[0]
    previous = versions[1] if len(versions) > 1 else None

    if not previous:
        logger.warning("Only one version exists; cannot restore to previous.")
        if args.force_rebuild:
            logger.step("Removing corrupted state (--force-rebuild)")
            if delete_object(bucket, key, bucket_region):
                logger.success("State removed. Run tofu apply and import existing resources.")
            sys.exit(0)
        sys.exit(1)

    prev_id = previous.get("VersionId")
    prev_modified = previous.get("LastModified", "?")
    logger.info(f"Current version: {current.get('VersionId')} ({current.get('LastModified')})")
    logger.info(f"Restoring to:    {prev_id} ({prev_modified})")

    if args.dry_run:
        logger.info("[DRY-RUN] Would restore to previous version. Run without --dry-run to apply.")
        sys.exit(0)

    if copy_object_version(bucket, key, prev_id, bucket_region):
        logger.success("State restored from previous version.")
    else:
        logger.error("Restore failed.")
        sys.exit(1)

    logger.step("Verifying durable outputs...")
    if verify_durable_outputs(args.env, region):
        logger.success("Durable state recovery complete.")
    else:
        logger.warning("Verification inconclusive. Run: tofu output (in durable dir) to check.")

    if args.refresh:
        _run_refresh(args.env, region)


def _run_refresh(env: str, region: str) -> None:
    """Run tofu refresh on durable and nonkube to sync state with AWS."""
    from tools.aws.scope_shared.core.terra_init import init_stack
    from tools.aws.scope_shared.core.terra_runner import terra_capture

    stacks = [
        ("durable", DURABLE_STACK),
        ("nonkube", "infra_terraform/live_deploy/aws/nonkube"),
    ]
    for name, stack_dir in stacks:
        logger.step(f"Refreshing {name} state...")
        init_stack(stack_dir, env, region)
        result = terra_capture(["refresh", "-input=false", "-lock=false"], cwd=stack_dir, region=region)
        if result.returncode == 0:
            logger.success(f"{name} refresh OK")
        else:
            logger.warning(f"{name} refresh had issues: {result.stderr or result.stdout}")


if __name__ == "__main__":
    main()
