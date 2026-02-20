"""
AWS Teardown Orchestrator

Usage:
  python tools/aws/teardown.py --scope kube --env dev --non-interactive
  python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
  python tools/aws/teardown.py --scope all --env dev --non-interactive

Rules:
- Never destroys infra_terraform/live_deploy/aws/scope_shared/durable.
- `all` destroys: nonkube -> kube -> shared-nondurable.
- Before destroying kube: removes CronJob + Job (scheduler + bootstrap).
- Before destroying nonkube: removes EventBridge rule, scales ECS service to 0, drains tasks; then destroy.
- Retry logic: configurable via config/retry_config.json (retriable/non-retriable patterns).

EventBridge rule: Defined in Terraform (infra_terraform/modules/aws/ecs). We remove via CLI in pre_destroy
because: (1) timing - must stop rule from firing before draining ECS; (2) orphan safety - if state
is empty, destroy is no-op and rule stays; CLI delete handles both in-state and orphaned rules.

EKS security groups: Created by AWS (not Terraform) as side effects of aws_eks_cluster/
aws_eks_node_group. AWS does not always delete them on cluster destroy. Post-destroy CLI
cleanup is the common industry practice. See README_WAR_STORIES ##41.
"""
import argparse
import json
import os
import subprocess
import sys

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.aws.scope_shared.core.backend import resolve_region
from tools.cloud_shared.stats import TeardownStats, scope_for
from tools.aws.scope_shared.core.phases import PhaseTracker, teardown_phases
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.deploy.bootstrap_helpers import k8s_remove_bootstrap_and_scheduler
from tools.aws.scope_shared.teardown.cloudfront_pre_destroy import pre_destroy_cloudfront
from tools.aws.kube.teardown_orphan_cleanup import remove_orphaned_eks_security_groups
from tools.cloud_shared.retry import run_with_retry, run_with_heartbeat
from tools.aws.scope_shared.core.terra_runner import get_terra_env

load_dotenv()

# Heartbeat interval for long-running tofu init/destroy. Default 10s so feedback appears sooner than deploy's 30s.
TEARDOWN_HEARTBEAT_INTERVAL_SEC = int(os.getenv("TEARDOWN_HEARTBEAT_INTERVAL_SEC", "10"))

ORDER = {
    "kube": ["infra_terraform/live_deploy/aws/kube"],
    "nonkube": ["infra_terraform/live_deploy/aws/nonkube"],
    "all": ["infra_terraform/live_deploy/aws/nonkube", "infra_terraform/live_deploy/aws/kube", "infra_terraform/live_deploy/aws/scope_shared/nondurable"],
}
DURABLE_STACK = "infra_terraform/live_deploy/aws/scope_shared/durable"

# Stacks that have CloudFront frontend (require pre-destroy before tofu destroy)
STACKS_WITH_CLOUDFRONT = tuple(ORDER["nonkube"] + ORDER["kube"])


def pre_destroy_kube(env: str, region: str | None = None, stats: TeardownStats | None = None):
    """
    Remove CronJob, Job, namespace, and orphaned EKS SGs before kube destroy.

    Why needed: EKS cluster deletion is blocked by LoadBalancer services (hold ENIs),
    running pods, and CronJobs/Jobs. Terraform cannot destroy the cluster until these are gone.

    Why not Terraform: K8s resources (Namespace, Deployment, Service, CronJob, Job) are
    applied via kubectl (kube_apply.py), not in Terraform state. We could move them into
    Terraform (kubernetes provider), but templating, provider config, and secret wiring
    add complexity—we choose kubectl pre-destroy. Orphan SGs: when state is empty,
    destroy is no-op; we remove them via CLI. See README_WAR_STORIES ##40.
    """
    try:
        k8s_remove_bootstrap_and_scheduler(env, region, stats=stats)
        remove_orphaned_eks_security_groups(env, region, stats=stats)
        logger.info("Pre-destroy: removed kube CronJob, Job, and orphaned EKS SGs.")
    except Exception as e:
        logger.warning(f"Pre-destroy warning (kube): {e}")


def pre_destroy_nonkube(env: str, region: str | None = None, stats: TeardownStats | None = None):
    """
    Drain ECS tasks before nonkube destroy.

    Why needed: ECS cluster deletion fails (ClusterContainsTasksException) while tasks
    are running. EventBridge can fire new Spark tasks during destroy. We must stop the
    rule, scale service to 0, and drain before Terraform destroy.

    Why not Terraform: EventBridge and ECS are in Terraform, but (1) timing—we must
    stop the rule from firing before drain; Terraform destroy order may not guarantee
    that. (2) Standalone tasks—EventBridge RunTask creates tasks outside the ECS
    service; Terraform does not manage those ephemeral tasks. (3) Orphan safety—if
    state is empty, destroy is no-op and rule stays; CLI delete handles both cases.

    Steps: Remove EventBridge rule, scale ECS service to 0, stop remaining tasks, wait.
    """
    import time

    region = region or resolve_region(None)
    prefix = os.getenv("FRU_PREFIX", "fru")
    cluster = os.getenv("ECS_CLUSTER_NAME") or f"{prefix}-{env}-ecs"
    service = f"{prefix}-{env}-api-svc"
    rule_name = f"{prefix}-{env}-spark-schedule"

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    logger.step("Pre-destroy: Draining ECS tasks (scale service to 0, disable EventBridge)...")

    # EventBridge rule: Terraform manages it (ecs module). CLI here for timing (stop
    # firing before drain) and orphan safety (empty state -> destroy no-op).
    def _remove_eventbridge_rule():
        try:
            subprocess.run(
                ["aws", "events", "disable-rule", "--name", rule_name, "--region", region],
                check=False,
                capture_output=True,
            )
            # EventBridge requires targets removed before delete; ignore if rule/targets don't exist
            out = subprocess.run(
                ["aws", "events", "list-targets-by-rule", "--rule", rule_name, "--region", region],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode == 0:
                try:
                    data = json.loads(out.stdout or "{}")
                    ids = [t["Id"] for t in data.get("Targets", [])]
                    if ids:
                        subprocess.run(
                            ["aws", "events", "remove-targets", "--rule", rule_name, "--ids"] + ids + ["--region", region],
                            check=False,
                            capture_output=True,
                        )
                except (json.JSONDecodeError, KeyError):
                    pass
            subprocess.run(
                ["aws", "events", "delete-rule", "--name", rule_name, "--region", region],
                check=False,
                capture_output=True,
            )
            logger.info(f"Removed EventBridge rule: {rule_name}")
        except Exception as e:
            logger.warning(f"Could not remove EventBridge rule: {e}")
    _timed("EventBridge rule", rule_name, _remove_eventbridge_rule)

    # Scale ECS service to 0
    def _scale_service():
        scale_out = subprocess.run(
            [
                "aws", "ecs", "update-service",
                "--cluster", cluster,
                "--service", service,
                "--desired-count", "0",
                "--region", region,
            ],
            capture_output=True,
            text=True,
        )
        if scale_out.returncode == 0:
            logger.info(f"Scaled ECS service {service} to 0")
        elif "ServiceNotFoundException" in (scale_out.stderr or ""):
            logger.info("ECS service already gone, skipping scale")
        else:
            logger.warning(f"Could not scale ECS service: {scale_out.stderr or scale_out.stdout}")
    _timed("ECS service (scale to 0)", f"{service} (cluster={cluster})", _scale_service)

    # Stop any remaining tasks (e.g. EventBridge-triggered Spark tasks)
    def _drain_tasks():
        for attempt in range(12):  # Wait up to 2 min
            out = subprocess.run(
                ["aws", "ecs", "list-tasks", "--cluster", cluster, "--region", region, "--output", "json"],
                capture_output=True,
                text=True,
            )
            if out.returncode != 0:
                break
            try:
                data = json.loads(out.stdout or "{}")
                tasks = data.get("taskArns", [])
            except json.JSONDecodeError:
                break
            if not tasks:
                logger.info("All ECS tasks drained.")
                break
            for arn in tasks[:10]:  # Stop in batches
                task_id = arn.split("/")[-1]
                subprocess.run(
                    ["aws", "ecs", "stop-task", "--cluster", cluster, "--task", task_id, "--region", region],
                    check=False,
                    capture_output=True,
                )
            logger.info(f"Stopping {len(tasks)} task(s)... (attempt {attempt + 1}/12)")
            time.sleep(10)
    _timed("ECS tasks (drain)", cluster, _drain_tasks)

    logger.success("Pre-destroy: ECS tasks drained.")


def destroy_stack(stack_dir: str, env: str, region: str | None = None, stats: TeardownStats | None = None):
    """Init + destroy. Retry on configurable retriable errors (config/retry_config.json)."""
    def _do():
        init_stack(stack_dir, env, region)
        base = get_base_vars(env, region)

        extra = []
        if "kube" in stack_dir and "nonkube" not in stack_dir:
            cluster_name = os.getenv("EKS_CLUSTER_NAME")
            if cluster_name:
                extra += ["-var", f"eks_cluster_name={cluster_name}"]

        cmd = [os.getenv("FRU_TF_BIN", "tofu"), "destroy", "-lock=false", "-auto-approve"] + base + extra
        description = f"tofu destroy in {stack_dir}"
        run_with_retry(
            cmd,
            cwd=stack_dir,
            env=get_terra_env(region),
            description=description,
            heartbeat_interval_sec=TEARDOWN_HEARTBEAT_INTERVAL_SEC,
            stream_output=True,  # Stream tofu destroy so user sees per-resource progress
        )

    if stats:
        with stats.timed("Tofu stack", stack_dir):
            _do()
    else:
        _do()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scope",
        choices=["kube", "nonkube", "all"],
        default=os.getenv("DEFAULT_SCOPE", "nonkube"),
        help="Teardown scope (default: DEFAULT_SCOPE from .env or nonkube)",
    )
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--incl-dura", action="store_true", help="Include shared durable stack in destroy (scope=all only)")
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    args = ap.parse_args()

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
    os.environ["CLOUD_REGION"] = region
    os.environ["PYTHONUNBUFFERED"] = "1"  # Flush output immediately (avoids silent hang when run under Cursor/CI)

    token = f"{args.scope}-{args.env}-destroy"

    if not args.non_interactive:
        resp = input(f"Type '{token}' to confirm: ").strip()
        if resp != token:
            raise SystemExit("Confirmation failed. Exiting.")

    stacks_to_destroy = list(ORDER[args.scope])
    if args.incl_dura and args.scope == "all":
        stacks_to_destroy.append(DURABLE_STACK)
        logger.info(f"Including durable stack (--incl-dura): will destroy after shared-nondurable")

    phases = teardown_phases(args.scope)
    if args.incl_dura and args.scope == "all":
        phases = phases + ["Destroy shared-durable"]
    tracker = PhaseTracker("Teardown", phases)
    stats = TeardownStats()
    phase_idx = 0

    logger.step(f"Starting teardown: scope={args.scope} env={args.env} region={region}")

    for s in stacks_to_destroy:
        phase_idx += 1
        tracker.start_phase(phase_idx)
        # Pre-destroy steps use scope "pre-destroy"
        stats.set_scope("pre-destroy")
        if s in ORDER["nonkube"]:
            logger.step(f"[{phase_idx}/{len(phases)}] Pre-destroy (drain ECS), then destroy...")
            pre_destroy_nonkube(args.env, region, stats=stats)
        elif s in ORDER["kube"]:
            logger.step(f"[{phase_idx}/{len(phases)}] Pre-destroy (broad kube cleanup), then destroy...")
            pre_destroy_kube(args.env, region, stats=stats)
        if s in STACKS_WITH_CLOUDFRONT:
            pre_destroy_cloudfront(s, args.env, region, stats=stats)
        # Tofu destroy uses stack scope (nonkube, kube, shared-nondurable)
        stats.set_scope(scope_for(s))
        logger.step(f"[{phase_idx}/{len(phases)}] Destroying {s}...")
        destroy_stack(s, args.env, region, stats=stats)
        tracker.end_phase(phase_idx)

    stats.print_summary()
    logger.success("Done." + (" (Shared durable remains.)" if not (args.incl_dura and args.scope == "all") else ""))


if __name__ == "__main__":
    main()
