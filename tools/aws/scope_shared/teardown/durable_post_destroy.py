"""
Post-destroy cleanup for durable stack (full teardown with --incl-dura).

Runs after all stacks are destroyed. Removes AWS-created orphans that Terraform
never managed:

1. RDS log group: AWS creates /aws/rds/cluster/{cluster}/postgresql when Aurora
   has enabled_cloudwatch_logs_exports. RDS does not delete it when the cluster
   is destroyed.

2. ECS Container Insights log group: AWS creates
   /aws/ecs/containerinsights/{cluster}/performance when Container Insights is
   enabled. ECS does not delete it when the cluster is destroyed.

3. State bucket: Created by setup_state_backend.py (not Terraform). Holds
   Terraform state; cannot be destroyed while teardown runs. After all stacks
   are gone, we empty and delete it. Next deploy will recreate via setup_state_backend.

4. DynamoDB lock table (optional): If TF_LOCK_TABLE_COMPONENT or TF_LOCK_TABLE_PREFIX
   is set, we delete the lock table for the region. Next deploy recreates it via setup_state_backend.

All operations are idempotent (ignore ResourceNotFoundException, NoSuchBucket).
"""
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats


def post_destroy_durable_orphans(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Remove orphaned resources after durable (and all) stacks are destroyed.

    Call only when --incl-dura and scope=all. Runs after the teardown loop.
    """
    from tools.cloud_shared.logging import logger
    from tools.aws.scope_shared.core.backend import (
        resolve_state_bucket,
        resolve_state_lock_table,
    )
    from tools.aws.scope_shared.core import resource_names

    proj = resource_names.get_proj_prefix()

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    logger.step("Post-destroy: removing durable orphans (log groups, state bucket, lock table)...")

    # 1. RDS log group: /aws/rds/cluster/{proj}-{env}-aurora-cluster/postgresql
    def _delete_rds_log_group():
        name = resource_names.rds_log_group(env)
        r = subprocess.run(
            ["aws", "logs", "delete-log-group", "--log-group-name", name, "--region", region],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            logger.info(f"Deleted RDS log group: {name}")
        elif "ResourceNotFoundException" in (r.stderr or ""):
            logger.info(f"RDS log group already gone: {name}")
        else:
            logger.warning(f"Could not delete RDS log group {name}: {r.stderr or r.stdout}")

    _timed("RDS log group", f"{proj}-{env}-aurora-cluster/postgresql", _delete_rds_log_group)

    # 2. ECS Container Insights log group: /aws/ecs/containerinsights/{proj}-{env}-cluster/performance
    def _delete_ecs_log_group():
        name = resource_names.ecs_container_insights_log_group(env)
        r = subprocess.run(
            ["aws", "logs", "delete-log-group", "--log-group-name", name, "--region", region],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            logger.info(f"Deleted ECS Container Insights log group: {name}")
        elif "ResourceNotFoundException" in (r.stderr or ""):
            logger.info(f"ECS log group already gone: {name}")
        else:
            logger.warning(f"Could not delete ECS log group {name}: {r.stderr or r.stdout}")

    _timed("ECS log group", f"{proj}-{env}-cluster/performance", _delete_ecs_log_group)

    # 3. State bucket: empty (all versions + delete markers) then delete
    # Versioned buckets: aws s3 rb --force does not remove old versions; use boto3.
    def _delete_state_bucket():
        try:
            bucket = resolve_state_bucket(region)
        except Exception as e:
            logger.warning(f"Could not resolve state bucket: {e}")
            return
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3 = boto3.client("s3", region_name=region)
            paginator = s3.get_paginator("list_object_versions")
            to_delete: list[dict] = []
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Versions", []) or []:
                    to_delete.append({"Key": obj["Key"], "VersionId": obj["VersionId"]})
                for obj in page.get("DeleteMarkers", []) or []:
                    to_delete.append({"Key": obj["Key"], "VersionId": obj["VersionId"]})
            while to_delete:
                batch = to_delete[:1000]
                to_delete = to_delete[1000:]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
            s3.delete_bucket(Bucket=bucket)
            logger.info(f"Deleted state bucket: {bucket}")
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchBucket":
                logger.info(f"State bucket already gone: {bucket}")
            else:
                logger.warning(f"Could not delete state bucket {bucket}: {e}")
        except Exception as e:
            logger.warning(f"Could not delete state bucket {bucket}: {e}")

    _timed("State bucket", region, _delete_state_bucket)

    # 4. DynamoDB lock table (if used)
    def _delete_lock_table():
        table = resolve_state_lock_table(region)
        if not table:
            return
        r = subprocess.run(
            ["aws", "dynamodb", "delete-table", "--table-name", table, "--region", region],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            logger.info(f"Deleted lock table: {table}")
        elif "ResourceNotFoundException" in (r.stderr or ""):
            logger.info(f"Lock table already gone: {table}")
        else:
            logger.warning(f"Could not delete lock table {table}: {r.stderr or r.stdout}")

    table = resolve_state_lock_table(region)
    if table:
        _timed("Lock table", table, _delete_lock_table)

    logger.success("Post-destroy: durable orphans removed.")
