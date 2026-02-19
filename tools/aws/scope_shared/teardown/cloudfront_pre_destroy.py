"""
Pre-destroy CloudFront distribution and OAC via AWS API before tofu destroy.

CloudFront distribution deletion is async; Terraform removes it from state immediately
but AWS takes 15-30 min to fully delete. OAC cannot be deleted while distribution
references it. This pre-destroy:
  1. Disables distribution, waits for Deployed, deletes, waits for 404
  2. Deletes OAC by name (sync; no wait needed once distribution is gone)

Handles orphaned OAC (removed from state via state rm): we delete it via API so no
import is needed on next deploy.

Resolves distribution ID: tofu output first (from state), fallback to comment search.
OAC: looked up by name {prefix}-{env}-frontend-{suffix}-oac.
"""
import os
import subprocess
import time

from tools.cloud_shared.logging import logger
from tools.cloud_shared.stats import TeardownStats
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_runner import get_terra_env

TIMEOUT_SEC = int(os.environ.get("CLOUDFRONT_PRE_DESTROY_TIMEOUT_SEC", "1800"))
POLL_INTERVAL_SEC = int(os.environ.get("CLOUDFRONT_PRE_DESTROY_POLL_INTERVAL_SEC", "30"))

OUTPUT_NAME = "cloudfront_distribution_id"


def _suffix_from_stack_dir(stack_dir: str) -> str:
    """Extract suffix (nonkube, kube) from stack path."""
    if "nonkube" in stack_dir:
        return "nonkube"
    if "kube" in stack_dir:
        return "kube"
    return ""


def _is_valid_distribution_id(s: str) -> bool:
    """CloudFront distribution IDs are alphanumeric, typically 13-14 chars (e.g. E38WH94IF9Y8BW)."""
    return bool(s) and len(s) >= 10 and len(s) <= 20 and s.isalnum()


def _get_distribution_id_from_tofu(stack_dir: str, env: str, region: str | None) -> str | None:
    """Get distribution ID from tofu output. Returns None if output missing or init fails."""
    try:
        init_stack(stack_dir, env, region)
        exe = os.getenv("FRU_TF_BIN", "tofu")
        result = subprocess.run(
            [exe, "output", "-raw", OUTPUT_NAME],
            cwd=stack_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=get_terra_env(region),
        )
        if result.returncode == 0 and result.stdout:
            raw = result.stdout.strip()
            if _is_valid_distribution_id(raw):
                return raw
    except Exception:
        pass
    return None


def _find_distribution_id_by_comment(comment: str, region: str) -> str | None:
    """Find CloudFront distribution ID by comment. CloudFront is global (no region)."""
    import boto3

    client = boto3.client("cloudfront")
    paginator = client.get_paginator("list_distributions")
    for page in paginator.paginate():
        for item in page.get("DistributionList", {}).get("Items", []):
            if item.get("Comment") == comment:
                return item.get("Id")
    return None


def _is_no_such_distribution(e: Exception) -> bool:
    from botocore.exceptions import ClientError

    return isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "NoSuchDistribution"


def _is_no_such_oac(e: Exception) -> bool:
    from botocore.exceptions import ClientError

    return isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "NoSuchOriginAccessControl"


def _is_oac_in_use(e: Exception) -> bool:
    from botocore.exceptions import ClientError

    return isinstance(e, ClientError) and e.response.get("Error", {}).get("Code") == "OriginAccessControlInUse"


def _find_oac_id_by_name(client, name: str) -> str | None:
    """Find OAC ID by name. CloudFront is global."""
    paginator = client.get_paginator("list_origin_access_controls")
    for page in paginator.paginate():
        for item in page.get("OriginAccessControlList", {}).get("Items", []):
            if item.get("Name") == name:
                return item.get("Id")
    return None


def _delete_oac(client, oac_id: str) -> None:
    """Delete OAC. Requires ETag from get_origin_access_control."""
    resp = client.get_origin_access_control(Id=oac_id)
    etag = resp.get("ETag")
    if not etag:
        raise RuntimeError(f"OAC {oac_id}: no ETag in get response")
    client.delete_origin_access_control(Id=oac_id, IfMatch=etag)


def _wait_for_deployed(dist_id: str, timeout_sec: int) -> bool:
    """Poll until distribution status is Deployed."""
    import boto3

    client = boto3.client("cloudfront")
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            resp = client.get_distribution(Id=dist_id)
            status = resp.get("Distribution", {}).get("Status")
            if status == "Deployed":
                return True
        except Exception as e:
            if _is_no_such_distribution(e):
                return True  # Already gone
            raise
        time.sleep(POLL_INTERVAL_SEC)
    return False


def _wait_for_gone(dist_id: str, timeout_sec: int) -> bool:
    """Poll until distribution returns 404."""
    import boto3

    client = boto3.client("cloudfront")
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            client.get_distribution(Id=dist_id)
        except Exception as e:
            if _is_no_such_distribution(e):
                return True
            raise
        time.sleep(POLL_INTERVAL_SEC)
    return False


def pre_destroy_cloudfront(
    stack_dir: str,
    env: str,
    region: str | None = None,
    stats: TeardownStats | None = None,
) -> None:
    """
    Disable and delete CloudFront distribution before tofu destroy so OAC can be removed.

    Resolves distribution ID: tofu output first (from state), fallback to comment search.
    Disables, waits for propagation, deletes, waits for 404. Skips if not found.
    """
    import boto3

    region = region or os.getenv("CLOUD_REGION", os.getenv("AWS_REGION", "us-east-1"))
    prefix = os.getenv("FRU_PREFIX", "fru")
    suffix = _suffix_from_stack_dir(stack_dir)
    if not suffix:
        return

    dist_id = _get_distribution_id_from_tofu(stack_dir, env, region)
    if not dist_id:
        comment = f"{prefix}-{env}-frontend-{suffix}"
        dist_id = _find_distribution_id_by_comment(comment, region)
    if not dist_id:
        logger.info(f"Pre-destroy CloudFront: no distribution found (terra output or comment). Will still try to delete orphaned OAC.")

    def _do():
        client = boto3.client("cloudfront")

        if dist_id:
            # 1. Disable (distribution may already be gone if state was stale)
            try:
                cfg_resp = client.get_distribution_config(Id=dist_id)
            except Exception as e:
                if _is_no_such_distribution(e):
                    logger.info(f"Pre-destroy CloudFront: distribution {dist_id} not found, skipping to OAC.")
                else:
                    raise
            else:
                etag = cfg_resp["ETag"]
                config = cfg_resp["DistributionConfig"]
                config["Enabled"] = False
                client.update_distribution(Id=dist_id, IfMatch=etag, DistributionConfig=config)

                # 2. Wait for Deployed
                half = TIMEOUT_SEC // 2
                if not _wait_for_deployed(dist_id, half):
                    raise RuntimeError(f"CloudFront {dist_id} did not reach Deployed within {half}s")

                # 3. Delete
                cfg_resp = client.get_distribution_config(Id=dist_id)
                etag = cfg_resp["ETag"]
                client.delete_distribution(Id=dist_id, IfMatch=etag)

                # 4. Wait for 404
                if not _wait_for_gone(dist_id, half):
                    raise RuntimeError(f"CloudFront {dist_id} did not disappear within {half}s")

                logger.info(f"Pre-destroy CloudFront: distribution {dist_id} deleted.")

        # 5. Delete OAC (sync; distribution is gone or was never found, so OAC can be deleted if orphaned)
        oac_name = f"{prefix}-{env}-frontend-{suffix}-oac"
        oac_id = _find_oac_id_by_name(client, oac_name)
        if oac_id:
            try:
                _delete_oac(client, oac_id)
                logger.info(f"Pre-destroy CloudFront: OAC {oac_id} ({oac_name}) deleted.")
            except Exception as e:
                if _is_no_such_oac(e):
                    logger.info(f"Pre-destroy CloudFront: OAC {oac_name} already gone, skipping.")
                elif _is_oac_in_use(e):
                    logger.warning(f"Pre-destroy CloudFront: OAC {oac_name} still in use (distribution not fully deleted?), skipping.")
                else:
                    raise
        else:
            logger.info(f"Pre-destroy CloudFront: OAC {oac_name} not found, skipping.")

    if stats:
        with stats.timed("CloudFront pre-destroy", stack_dir):
            _do()
    else:
        _do()
