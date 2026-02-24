"""
Import pre-existing nonkube stack resources into Terraform state.

Resources: IAM roles, S3 frontend bucket, CloudFront OAC, ECS-layer resources
(CloudWatch log groups, ALB, target group, security groups). When these exist in AWS
but not in state (e.g. after brutal removal or partial teardown), apply fails with
EntityAlreadyExists / ResourceAlreadyExistsException.

Broader import for convenience; ideal approach (import IAM only, destroy/recreate others)
documented in docs/learned/terra/TERRA_LEARN_IMPORT_PREEXIST.md.
"""
import json
import subprocess

from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_runner import get_terra_env
from tools.aws.scope_shared.import_preexist._common import (
    import_batch,
    import_one_resource,
    sg_rule_import_id,
    state_contains,
)


def _aws_json(cmd: list[str], region: str | None, env: dict | None = None) -> dict:
    """Run AWS CLI, return parsed JSON. Returns {} on failure."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    try:
        out = subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=30,
            env=env or None,
        )
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    return {}


def _get_account_id(region: str | None = None) -> str:
    """Get current AWS account ID."""
    data = _aws_json(["sts", "get-caller-identity"], None, get_terra_env(region))
    return data.get("Account", "")


def _find_frontend_bucket(prefix: str, env: str, suffix: str, region: str, region_str: str) -> str:
    """Find existing frontend bucket by listing S3 (fallback when account_id unavailable)."""
    data = _aws_json(["s3api", "list-buckets"], None, get_terra_env(region))
    buckets = data.get("Buckets", [])
    pattern = f"{prefix}-{env}-frontend-{suffix}-{region_str}-"
    for b in buckets:
        name = b.get("Name", "")
        if name.startswith(pattern):
            return name
    return ""


def _get_oac_id(name: str, region: str | None = None) -> str:
    """Get CloudFront OAC ID by name. CloudFront API is global, endpoint is us-east-1 only."""
    env = get_terra_env(region)
    marker = ""
    while True:
        cmd = ["cloudfront", "list-origin-access-controls", "--max-items", "100"]
        if marker:
            cmd += ["--marker", marker]
        data = _aws_json(cmd, "us-east-1", env)
        oac_list = data.get("OriginAccessControlList", {})
        for item in oac_list.get("Items") or []:
            if item.get("Name") == name:
                return item.get("Id", "")
        marker = oac_list.get("NextMarker", "")
        if not marker:
            break
    return ""


def _get_alb_arn(name: str, region: str | None = None) -> str:
    """Get ALB ARN by name. Returns empty if not found."""
    data = _aws_json(
        ["elbv2", "describe-load-balancers", "--names", name],
        region,
        get_terra_env(region),
    )
    lbs = data.get("LoadBalancers", [])
    return lbs[0].get("LoadBalancerArn", "") if lbs else ""


def _get_target_group_arn(name: str, region: str | None = None) -> str:
    """Get target group ARN by name. Returns empty if not found."""
    data = _aws_json(
        ["elbv2", "describe-target-groups", "--names", name],
        region,
        get_terra_env(region),
    )
    tgs = data.get("TargetGroups", [])
    return tgs[0].get("TargetGroupArn", "") if tgs else ""


def _get_sg_id_by_name(name: str, region: str | None = None) -> str:
    """Get security group ID by group name. Returns empty if not found."""
    data = _aws_json(
        ["ec2", "describe-security-groups", "--filters", f"Name=group-name,Values={name}"],
        region,
        get_terra_env(region),
    )
    sgs = data.get("SecurityGroups", [])
    return sgs[0].get("GroupId", "") if sgs else ""


def _get_durable_output(output_key: str, env: str, region: str | None) -> str:
    """Get output value from shared_durable stack. Returns empty if unavailable."""
    try:
        from tools.aws.scope_shared.deploy.deploy_common import tofu_output_json

        durable = tofu_output_json("infra_terraform/live_deploy/aws/scope_shared/durable", env, region)
        obj = durable.get(output_key, {})
        return obj.get("value", "") if isinstance(obj, dict) else ""
    except Exception:
        return ""


def run_import_nonkube(
    stack_dir: str,
    env: str,
    region: str | None = None,
    prefix: str = "fru",
) -> int:
    """
    Import pre-existing nonkube resources. Returns count of failures.
    Safe to run always; skips non-existent and already-in-state.
    Bucket name derived from --cloud-region: {prefix}-{env}-frontend-nonkube-{region}-{account_id}
    """
    logger.step("Importing pre-existing nonkube resources into state")
    failed = 0
    deploy_region = region or "us-east-1"

    # S3 bucket: prefix-env-frontend-nonkube-{region}-{account_id} (matches Terraform)
    account_id = _get_account_id(region)
    bucket_name = f"{prefix}-{env}-frontend-nonkube-{deploy_region}-{account_id}" if account_id else ""
    if not bucket_name:
        bucket_name = _find_frontend_bucket(prefix, env, "nonkube", region, deploy_region)
    s3_addr = "module.frontend.aws_s3_bucket.frontend"
    if bucket_name:
        logger.info(f"  S3 bucket: attempting import {s3_addr} <- {bucket_name}")
        ok = import_one_resource(
            stack_dir,
            s3_addr,
            bucket_name,
            region,
            verbose=True,
            allow_skip_nonexistent=True,  # skip if bucket doesn't exist; apply will create; cross-region orphan is special case
        )
        if not ok:
            failed += 1
        elif not state_contains(stack_dir, s3_addr, region):
            # With allow_skip=True, "OK" may mean we skipped (bucket doesn't exist); not in state is expected
            logger.info(f"  S3 bucket not in state (skipped or will be created by apply)")
    else:
        logger.warning("  Skip S3 bucket: could not get account ID or find bucket")

    # IAM roles (ID = role name)
    # Region suffix: per-region names avoid cross-region teardown deleting shared roles
    role_specs = [
        ("module.ecs.aws_iam_role.exec", f"{prefix}-{env}-ecs-exec-{deploy_region}"),
        ("module.ecs.aws_iam_role.task", f"{prefix}-{env}-ecs-task-{deploy_region}"),
        ("module.ecs.aws_iam_role.spark_task_exec", f"{prefix}-{env}-spark-task-exec-{deploy_region}"),
        ("module.ecs.aws_iam_role.spark_task", f"{prefix}-{env}-spark-task-{deploy_region}"),
        ("module.ecs.aws_iam_role.events_invoke_ecs", f"{prefix}-{env}-events-invoke-ecs-{deploy_region}"),
    ]
    failed += import_batch(stack_dir, role_specs, region)

    # ECS-layer resources (CloudWatch, ALB, target group, security groups)
    # Naming matches infra_terraform/modules/aws/ecs/main.tf
    alb_name = f"{prefix}-{env}-alb"
    log_specs = [
        ("module.ecs.aws_cloudwatch_log_group.ecs", f"/fru/{env}/ecs-api"),
        ("module.ecs.aws_cloudwatch_log_group.spark", f"/fru/{env}/spark"),
    ]
    failed += import_batch(stack_dir, log_specs, region)

    # ALB and target group: import by ARN (look up by name)
    alb_arn = _get_alb_arn(alb_name, region)
    if alb_arn:
        logger.info("Importing module.ecs.aws_lb.main...")
        if not import_one_resource(
            stack_dir, "module.ecs.aws_lb.main", alb_arn, region, allow_skip_nonexistent=True
        ):
            failed += 1
    else:
        logger.info(f"  Skip ALB (not found in AWS): {alb_name}")

    tg_name = f"{alb_name}-tg"
    tg_arn = _get_target_group_arn(tg_name, region)
    if tg_arn:
        logger.info("Importing module.ecs.aws_lb_target_group.api...")
        if not import_one_resource(
            stack_dir,
            "module.ecs.aws_lb_target_group.api",
            tg_arn,
            region,
            allow_skip_nonexistent=True,
        ):
            failed += 1
    else:
        logger.info(f"  Skip target group (not found in AWS): {tg_name}")

    # Security groups: import by sg ID (look up by name)
    alb_sg_id = ""
    tasks_sg_id = ""
    for sg_name, addr in [
        (f"{alb_name}-sg", "module.ecs.aws_security_group.alb"),
        (f"{prefix}-ecs-tasks-sg", "module.ecs.aws_security_group.tasks"),
    ]:
        sg_id = _get_sg_id_by_name(sg_name, region)
        if sg_id:
            if "alb" in addr:
                alb_sg_id = sg_id
            else:
                tasks_sg_id = sg_id
            logger.info(f"Importing {addr}...")
            if not import_one_resource(
                stack_dir, addr, sg_id, region, allow_skip_nonexistent=True
            ):
                failed += 1
        else:
            logger.info(f"  Skip SG (not found in AWS): {sg_name}")

    # Security group rules: import when rules exist in AWS but not in state (InvalidPermission.Duplicate)
    # tasks_from_alb: ingress on tasks SG from ALB SG, port 5001
    # aurora_from_ecs: ingress on Aurora SG from tasks SG, port 5432 (conditional on aurora)
    container_port = 5001
    if alb_sg_id and tasks_sg_id:
        tasks_from_alb_id = sg_rule_import_id(
            tasks_sg_id, "ingress", "tcp", container_port, container_port, alb_sg_id
        )
        logger.info("Importing module.ecs.aws_security_group_rule.tasks_from_alb...")
        if not import_one_resource(
            stack_dir,
            "module.ecs.aws_security_group_rule.tasks_from_alb",
            tasks_from_alb_id,
            region,
            allow_skip_nonexistent=True,
        ):
            failed += 1

    aurora_sg_id = _get_durable_output("aurora_security_group_id", env, region)
    # Re-init nonkube after durable output (tofu may have switched context)
    from tools.aws.scope_shared.core.terra_init import init_stack

    init_stack(stack_dir, env, region)
    if aurora_sg_id and tasks_sg_id:
        aurora_from_ecs_id = sg_rule_import_id(
            aurora_sg_id, "ingress", "tcp", 5432, 5432, tasks_sg_id
        )
        logger.info("Importing module.ecs.aws_security_group_rule.aurora_from_ecs[0]...")
        if not import_one_resource(
            stack_dir,
            "module.ecs.aws_security_group_rule.aurora_from_ecs[0]",
            aurora_from_ecs_id,
            region,
            allow_skip_nonexistent=True,
        ):
            failed += 1

    # CloudFront OAC: import by OAC ID (look up by name). OAC is region-scoped (name includes region).
    oac_name = f"{prefix}-{env}-frontend-nonkube-{deploy_region}-oac"
    oac_id = _get_oac_id(oac_name, region)
    if oac_id:
        logger.info("  CloudFront OAC (region-scoped); adopting into state if it exists")
        if not import_one_resource(
            stack_dir,
            "module.frontend.aws_cloudfront_origin_access_control.frontend",
            oac_id,
            region,
        ):
            failed += 1
    else:
        logger.info(
            f"  Skip OAC (not found in AWS): {oac_name}. "
            "CloudFront API uses us-east-1; if OAC exists, apply may fail with OriginAccessControlAlreadyExists."
        )

    if failed == 0:
        logger.success("Import phase completed (nonkube)")
    else:
        logger.warning(f"Some imports failed ({failed}). Run 'tofu plan' to see remaining differences.")
    return failed
