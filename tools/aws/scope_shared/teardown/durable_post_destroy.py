"""
Post-destroy cleanup for durable stack (teardown with --incl-dura or --incl-dura-all).

Two functions, called separately by the teardown orchestrator:

1. post_destroy_durable_log_groups: RDS and ECS CloudWatch log groups.
   Called when durable is destroyed (--incl-dura or --incl-dura-all).
   AWS creates these as side effects; Terraform never manages them.

2. post_destroy_state_backend: State bucket and DynamoDB lock table.
   Called only when durable_with_cooloff is also destroyed (--incl-dura-all).
   When --incl-dura only, secrets remain and their state lives in the bucket;
   we keep the bucket to preserve that state for re-deploy.

All operations are idempotent (ignore ResourceNotFoundException, NoSuchBucket).
"""
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats


def _timed(stats: "TeardownStats | None", component: str, identifier: str, fn):
    if stats:
        with stats.timed(component, identifier):
            fn()
    else:
        fn()


def post_destroy_durable_log_groups(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Remove RDS and ECS CloudWatch log groups orphaned when durable is destroyed.

    Call when --incl-dura or --incl-dura-all and scope=all.
    """
    from tools.cloud_shared.logging import logger
    from tools.aws.scope_shared.core import resource_names

    proj = resource_names.get_proj_prefix()
    logger.step("Post-destroy: removing durable log groups (RDS, ECS)...")

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

    _timed(stats, "RDS log group", f"{proj}-{env}-aurora-cluster/postgresql", _delete_rds_log_group)

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

    _timed(stats, "ECS log group", f"{proj}-{env}-cluster/performance", _delete_ecs_log_group)
    logger.success("Post-destroy: durable log groups removed.")


def post_destroy_state_backend(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Remove state bucket and lock table. Call only when durable_with_cooloff was
    destroyed (--incl-dura-all). When --incl-dura only, secrets remain and their
    state lives in the bucket; we keep it for re-deploy.
    """
    from tools.cloud_shared.logging import logger
    from tools.aws.scope_shared.core.backend import (
        resolve_state_bucket,
        resolve_state_lock_table,
    )

    logger.step("Post-destroy: removing state backend (bucket, lock table)...")

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

    _timed(stats, "State bucket", region, _delete_state_bucket)

    table = resolve_state_lock_table(region)
    if table:
        def _delete_lock_table():
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

        _timed(stats, "Lock table", table, _delete_lock_table)

    logger.success("Post-destroy: state backend removed.")


def post_destroy_durable_orphans(
    env: str,
    region: str,
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Legacy: runs both log groups and state backend. Prefer calling
    post_destroy_durable_log_groups and post_destroy_state_backend directly
    so the orchestrator can choose when to delete the state backend.
    """
    post_destroy_durable_log_groups(env, region, stats)
    post_destroy_state_backend(env, region, stats)
