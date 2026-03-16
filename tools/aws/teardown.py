"""
AWS Teardown Orchestrator

Usage:
  python tools/aws/teardown.py --scope kube --env dev --non-interactive
  python tools/aws/teardown.py --scope nonkube --env dev --non-interactive
  python tools/aws/teardown.py --scope all --env dev --non-interactive

Rules:
- `all` destroys: nonkube -> kube -> shared-nondurable.
- `--incl-dura`: also destroy durable (VPC+Aurora); secrets remain. No 30-day block on re-deploy.
- `--incl-dura-all`: also destroy durable and durable_with_cooloff (secrets); full teardown.
- Before destroying kube: removes CronJob + Job (scheduler + bootstrap).
- Before destroying nonkube: removes EventBridge rule, scales ECS service to 0, drains tasks; then destroy.
- Import before destroy: runs import_preexist for each stack so orphaned resources are adopted into state and destroy can remove them (legacy pattern).
- Retry logic: configurable via config/retry_config.json (retriable/non-retriable patterns).

EventBridge rule: Defined in Terraform (infra_terraform/modules/aws/ecs). We remove via CLI in pre_destroy
because: (1) timing - must stop rule from firing before draining ECS; (2) orphan safety - if state
is empty, destroy is no-op and rule stays; CLI delete handles both in-state and orphaned rules.

EKS security groups: cluster-sg/nodes-sg created by AWS as side effects; k8s-elb-* created
by in-tree when Classic ELB Service exists. AWS does not always delete them. We remove
cluster-sg/nodes-sg in pre_destroy (if cluster gone); k8s-elb-* in post kube destroy,
before durable (blocks VPC delete). See docs/war_stories/WAR_STORIES_AWS.md ##23, ##6.

Post-destroy (--incl-dura): After all stacks destroyed, removes durable orphans:
RDS log group, ECS Container Insights log group, state bucket, lock table. Next
deploy recreates bucket/table via setup_state_backend.

Terraform variable requirements (TF_VAR_*):
  nonkube and kube stacks have required variables with no defaults. Without them,
  tofu import and tofu destroy prompt for input and hang. We set these from
  config before import/destroy:
  - nonkube: min_instance_count, max_instance_count, api_task_cpu, api_task_memory,
    spark_task_cpu, spark_task_memory (from get_nonkube_compute_config).
  - kube: eks_min_node_count, eks_max_node_count, eks_instance_types
    (from get_kube_compute_config).
  Config source: config/cloud/aws_deploy_config.yaml (nonkube/kube.compute).
  See docs/learned/cloud_shared/RESOURCE_ALLOCATION_CONFIG_YAML.md.
"""
import argparse
import json
import os
import subprocess
import sys
import time

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, EnvVarNotFound
from tools.aws.scope_shared.core.backend import resolve_region, resolve_state_bucket
from tools.aws.provider_config_handler import get_azs, get_subnet_cidrs
from tools.cloud_shared.stats import TeardownStats, scope_for
from tools.aws.scope_shared.core.phases import PhaseTracker, teardown_phases
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.kube.kube_pre_destroy import k8s_pre_destroy_cleanup
from tools.aws.scope_shared.import_preexist.nonkube import run_import_nonkube
from tools.aws.scope_shared.import_preexist.kube import run_import_kube
from tools.aws.scope_shared.teardown.cloudfront_pre_destroy import pre_destroy_cloudfront
from tools.aws.scope_shared.teardown.durable_post_destroy import (
    post_destroy_durable_log_groups,
    post_destroy_state_backend,
)
from tools.aws.kube.teardown_orphan_cleanup import (
    remove_orphaned_eks_security_groups,
    remove_orphaned_k8s_elb_security_groups,
)
from tools.cloud_shared.retry import run_with_retry, run_with_heartbeat
from tools.aws.scope_shared.core.terra_runner import get_terra_env

load_dotenv()

# Heartbeat interval for long-running tofu init/destroy. Default 10s so feedback appears sooner than deploy's 30s.
TEARDOWN_HEARTBEAT_INTERVAL_SEC = int(os.getenv("TEARDOWN_HEARTBEAT_INTERVAL_SEC", "10"))
# Optional timeout for tofu destroy (seconds). 0 or unset = no timeout. Use to avoid indefinite hangs (e.g. 7200 = 2h).
TEARDOWN_DESTROY_TIMEOUT_SEC = int(os.getenv("TEARDOWN_DESTROY_TIMEOUT_SEC", "0"))


def _state_bucket_exists(region: str | None) -> bool:
    """Return True if the Terraform state bucket exists. False when deleted by a previous teardown."""
    try:
        bucket = resolve_state_bucket(region or resolve_region(None))
        out = subprocess.run(
            ["aws", "s3api", "head-bucket", "--bucket", bucket],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return False


def _durable_has_outputs(env: str, region: str | None) -> bool:
    """
    Return True if durable stack has outputs (vpc_id). False when durable was already
    destroyed (e.g. from a previous partial teardown). Used to skip nonkube/kube
    when they cannot run (they reference durable outputs).
    """
    try:
        init_stack(DURABLE_STACK, env, region)
        result = subprocess.run(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=DURABLE_STACK,
            capture_output=True,
            text=True,
            timeout=30,
            env=get_terra_env(region),
        )
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout or "{}")
        vpc = data.get("vpc_id", {})
        val = vpc.get("value", "") if isinstance(vpc, dict) else ""
        return bool(val)
    except Exception:
        return False

ORDER = {
    "kube": ["infra_terraform/live_deploy/aws/kube"],
    "nonkube": ["infra_terraform/live_deploy/aws/nonkube"],
    "all": ["infra_terraform/live_deploy/aws/nonkube", "infra_terraform/live_deploy/aws/kube", "infra_terraform/live_deploy/aws/scope_shared/nondurable"],
}
DURABLE_STACK = "infra_terraform/live_deploy/aws/scope_shared/durable"
DURABLE_COOLOFF_STACK = "infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff"
NONDURABLE_STACK = "infra_terraform/live_deploy/aws/scope_shared/nondurable"
NONKUBE_STACK = "infra_terraform/live_deploy/aws/nonkube"
KUBE_STACK = "infra_terraform/live_deploy/aws/kube"

# Stacks that require the state bucket to exist (nondurable, durable, durable_with_cooloff)
STACKS_REQUIRING_STATE_BUCKET = (NONDURABLE_STACK, DURABLE_STACK, DURABLE_COOLOFF_STACK)

# Stacks that have CloudFront frontend (require pre-destroy before tofu destroy)
STACKS_WITH_CLOUDFRONT = tuple(ORDER["nonkube"] + ORDER["kube"])


def pre_destroy_kube(env: str, region: str | None = None, stats: TeardownStats | None = None):
    """
    Remove CronJob, Job, namespace, and orphaned EKS SGs before kube destroy.

    EKS cluster deletion is blocked by LoadBalancer services (hold ENIs), running pods,
    and CronJobs/Jobs. Terraform cannot destroy the cluster until these are gone. K8s
    resources are applied via kubectl (kube_apply.py), not Terraform—we use kubectl
    pre-destroy. Orphan cluster-sg/nodes-sg: removed here if cluster already gone.
    k8s-elb-* SGs (Classic ELB track) are removed post kube destroy, before durable.
    """
    try:
        k8s_pre_destroy_cleanup(env, region, stats=stats)
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

    from tools.aws.scope_shared.core import resource_names
    region = region or resolve_region(None)
    proj = resource_names.get_proj_prefix()
    cluster = resource_names.ecs_cluster(env, region)
    service = f"{proj}-{env}-api-svc"
    rule_name = f"{proj}-{env}-spark-schedule"

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
            if attempt == 0:
                logger.info(f"Pre-destroy nonkube: polling `aws ecs list-tasks --cluster {cluster} --region {region}` until drained")
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
                logger.info(f"Pre-destroy nonkube: running `aws ecs stop-task --cluster {cluster} --task {task_id}`")
                subprocess.run(
                    ["aws", "ecs", "stop-task", "--cluster", cluster, "--task", task_id, "--region", region],
                    check=False,
                    capture_output=True,
                )
            logger.info(f"Pre-destroy nonkube: stopping {len(tasks)} task(s)... (attempt {attempt + 1}/12)")
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
            from tools.aws.scope_shared.core import resource_names
            cluster_name = resource_names.eks_cluster(env, region or resolve_region(None))
            extra += ["-var", f"eks_cluster_name={cluster_name}"]

        # Durable stack requires aurora_master_password; without it tofu prompts and blocks.
        # Use exact match: "durable" in "nondurable" would incorrectly add these vars to nondurable.
        if stack_dir == DURABLE_STACK:
            aurora_pw = os.getenv("PGPASSWORD") or "placeholder"
            destroy_region = region or resolve_region(None)
            azs = get_azs(destroy_region)
            public_cidrs, private_cidrs = get_subnet_cidrs(destroy_region)
            azs_json = json.dumps(azs)
            public_json = json.dumps(public_cidrs)
            private_json = json.dumps(private_cidrs)
            extra += [
                "-var", f"azs={azs_json}",
                "-var", f"public_subnet_cidrs={public_json}",
                "-var", f"private_subnet_cidrs={private_json}",
                "-var", "allow_destroy_durable=true",
                "-var", f"aurora_master_password={aurora_pw}",
            ]
            if aurora_pw == "placeholder":
                logger.warning("PGPASSWORD not set; using placeholder for durable destroy (value not used for delete)")

        cmd = [os.getenv("FRU_TF_BIN", "tofu"), "destroy", "-lock=false", "-auto-approve"] + base + extra
        description = f"tofu destroy in {stack_dir}"
        run_with_retry(
            cmd,
            cwd=stack_dir,
            env=get_terra_env(region),
            description=description,
            heartbeat_interval_sec=TEARDOWN_HEARTBEAT_INTERVAL_SEC,
            stream_output=True,  # Stream tofu destroy so user sees per-resource progress
            timeout_sec=TEARDOWN_DESTROY_TIMEOUT_SEC if TEARDOWN_DESTROY_TIMEOUT_SEC > 0 else None,
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
    ap.add_argument("--incl-dura", action="store_true", help="Include durable (VPC+Aurora) in destroy; secrets remain (scope=all only)")
    ap.add_argument("--incl-dura-all", action="store_true", help="Include durable AND durable_with_cooloff (secrets) in destroy; full teardown (scope=all only)")
    ap.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    ap.add_argument(
        "--post-destroy-only",
        action="store_true",
        help="Skip stack destroy; only run post-destroy durable orphans (for testing full cleanup on already-torn-down region)",
    )
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

    # --post-destroy-only: skip destroy loop, run only durable orphans cleanup
    if args.post_destroy_only:
        if not ((args.incl_dura or args.incl_dura_all) and args.scope == "all"):
            logger.error("--post-destroy-only requires --incl-dura or --incl-dura-all and --scope all")
            sys.exit(1)
        logger.operation_start("Teardown (post-destroy only)", args.scope, args.env, region)
        stats = TeardownStats()
        try:
            post_destroy_durable_log_groups(args.env, region, stats=stats)
        except Exception as e:
            logger.warning(f"Post-destroy durable log groups: {e}")
        if args.incl_dura_all:
            try:
                post_destroy_state_backend(args.env, region, stats=stats)
            except Exception as e:
                logger.warning(f"Post-destroy state backend: {e}")
        logger.operation_end("Teardown (post-destroy only)", args.scope, args.env, region, 0, ok=True)
        logger.success("Done.")
        return

    stacks_to_destroy = list(ORDER[args.scope])
    if args.scope == "all":
        if args.incl_dura_all:
            # Full teardown: durable (VPC+Aurora) then durable_with_cooloff (secrets)
            stacks_to_destroy.append(DURABLE_STACK)
            stacks_to_destroy.append(DURABLE_COOLOFF_STACK)
            logger.info("Including durable + durable_with_cooloff (--incl-dura-all): full teardown")
        elif args.incl_dura:
            # Partial: durable only; secrets remain (no 30-day block on re-deploy)
            stacks_to_destroy.append(DURABLE_STACK)
            logger.info("Including durable only (--incl-dura): VPC+Aurora destroyed; secrets remain")

    phases = teardown_phases(args.scope)
    if args.incl_dura and args.scope == "all":
        phases = phases + ["Destroy shared-durable"]
    if args.incl_dura_all and args.scope == "all":
        phases = phases + ["Destroy durable_with_cooloff"]
    tracker = PhaseTracker("Teardown", phases)
    stats = TeardownStats()
    phase_idx = 0

    teardown_start = time.time()
    logger.operation_start("Teardown", args.scope, args.env, region)

    for s in stacks_to_destroy:
        phase_idx += 1
        tracker.start_phase(phase_idx)
        # When durable was already destroyed (e.g. previous partial teardown), nonkube/kube
        # cannot run: they reference data.terraform_remote_state.shared_durable.outputs
        # which is empty. Skip them; resources are gone anyway.
        if s in (NONKUBE_STACK, KUBE_STACK) and (args.incl_dura or args.incl_dura_all):
            if not _durable_has_outputs(args.env, region):
                B = "\033[1m"
                R = "\033[0m"
                stack_name = "nonkube" if s == NONKUBE_STACK else "kube"
                logger.info(
                    f"{B}SKIP {stack_name}:{R} Durable has no outputs (destroyed, never deployed, or state unavailable). "
                    f"{B}Why:{R} {stack_name} references durable outputs (vpc_id, subnets, secrets); "
                    f"without them, tofu cannot evaluate config. {B}Action:{R} Skipping—nothing to tear down or resources are already gone."
                )
                tracker.end_phase(phase_idx)
                continue
        # When state bucket was deleted by a previous teardown (post_destroy_state_backend),
        # we cannot init nondurable/durable stacks. Skip them—resources are already gone.
        if s in STACKS_REQUIRING_STATE_BUCKET and not _state_bucket_exists(region):
            B = "\033[1m"
            R = "\033[0m"
            stack_name = "nondurable" if s == NONDURABLE_STACK else ("durable" if s == DURABLE_STACK else "durable_with_cooloff")
            logger.info(
                f"{B}SKIP {stack_name}:{R} State bucket does not exist (deleted by previous teardown). "
                f"{B}Action:{R} Skipping—nothing to tear down."
            )
            tracker.end_phase(phase_idx)
            continue
        # Pre-destroy steps use scope "pre-destroy"
        stats.set_scope("pre-destroy")
        if s in ORDER["nonkube"]:
            logger.step(f"[{phase_idx}/{len(phases)}] Pre-destroy (drain ECS), then destroy...")
            pre_destroy_nonkube(args.env, region, stats=stats)
        elif s in ORDER["kube"]:
            logger.step(f"[{phase_idx}/{len(phases)}] Pre-destroy (broad kube cleanup), then destroy...")
            logger.info("Pre-destroy kube: removing CronJob, Job, namespace, orphan SGs...")
            pre_destroy_kube(args.env, region, stats=stats)
        if s in STACKS_WITH_CLOUDFRONT:
            stack_name = "kube" if "kube" in s else "nonkube"
            logger.info(f"Pre-destroy CloudFront for {stack_name} (CloudFront API: disable → wait Deployed → delete → wait 404)...")
            pre_destroy_cloudfront(s, args.env, region, stats=stats)
        # Import before destroy: reconcile state so destroy can remove orphaned resources (legacy pattern)
        if s == NONKUBE_STACK:
            logger.info("Reconciling nonkube state (import before destroy)...")
            init_stack(s, args.env, region)
            get_base_vars(args.env, region)
            # Nonkube stack requires compute vars (min/max instance, task cpu/memory) from config.
            # Without these, tofu import and destroy prompt for input and hang.
            deploy_region = region or resolve_region(None)
            from tools.aws.provider_config_handler import get_nonkube_compute_config
            cfg = get_nonkube_compute_config(deploy_region)
            tasks = cfg["tasks"]
            os.environ["TF_VAR_min_instance_count"] = str(cfg["min_instance_count"])
            os.environ["TF_VAR_max_instance_count"] = str(cfg["max_instance_count"])
            os.environ["TF_VAR_api_task_cpu"] = str(tasks["api"]["cpu"])
            os.environ["TF_VAR_api_task_memory"] = str(tasks["api"]["memory"])
            os.environ["TF_VAR_spark_task_cpu"] = str(tasks["spark"]["cpu"])
            os.environ["TF_VAR_spark_task_memory"] = str(tasks["spark"]["memory"])
            from tools.aws.scope_shared.core import resource_names
            run_import_nonkube(s, args.env, region, prefix=resource_names.get_proj_prefix())
        elif s == KUBE_STACK:
            logger.info("Reconciling kube state (import before destroy)...")
            init_stack(s, args.env, region)
            get_base_vars(args.env, region)
            # Kube stack requires EKS compute vars (min/max node count, instance types) from config.
            # Without these, tofu import and destroy prompt for input and hang.
            deploy_region = region or resolve_region(None)
            from tools.aws.provider_config_handler import get_kube_compute_config
            kube_cfg = get_kube_compute_config(deploy_region)
            os.environ["TF_VAR_eks_min_node_count"] = str(kube_cfg["min_node_count"])
            os.environ["TF_VAR_eks_max_node_count"] = str(kube_cfg["max_node_count"])
            os.environ["TF_VAR_eks_instance_types"] = json.dumps(kube_cfg["node_instance_types"])
            from tools.aws.scope_shared.core import resource_names
            run_import_kube(s, args.env, region, prefix=resource_names.get_proj_prefix(), eks_cluster_name=resource_names.eks_cluster(args.env, region))
        # Tofu destroy uses stack scope (nonkube, kube, shared-nondurable)
        stats.set_scope(scope_for(s))
        logger.step(f"[{phase_idx}/{len(phases)}] Destroying {s}...")
        destroy_stack(s, args.env, region, stats=stats)
        # Post kube destroy: remove k8s-elb-* SGs before durable (they block VPC delete)
        if s == KUBE_STACK:
            logger.info("Post kube destroy: removing orphaned k8s-elb-* security groups...")
            remove_orphaned_k8s_elb_security_groups(args.env, region, stats=stats)
        tracker.end_phase(phase_idx)

    # Post-destroy: when durable was destroyed, remove orphans
    if (args.incl_dura or args.incl_dura_all) and args.scope == "all":
        try:
            post_destroy_durable_log_groups(args.env, region, stats=stats)
        except Exception as e:
            logger.warning(f"Post-destroy durable log groups: {e}")
        if args.incl_dura_all:
            try:
                post_destroy_state_backend(args.env, region, stats=stats)
            except Exception as e:
                logger.warning(f"Post-destroy state backend: {e}")
        # Remove local Docker cache images used by this provider (same names as build_and_push leaves)
        try:
            from tools.aws.scope_shared.core import resource_names
            app_repo = resource_names.ecr_repo_app(args.env, region)
            spark_repo = resource_names.ecr_repo_spark(args.env, region)
            app_tag = os.getenv("APP_IMAGE_TAG", "latest")
            spark_tag = os.getenv("SPARK_IMAGE_TAG", "latest")
            refs = [f"{app_repo}:latest", f"{spark_repo}:latest"]
            if app_tag != "latest":
                refs.append(f"{app_repo}:{app_tag}")
            if spark_tag != "latest":
                refs.append(f"{spark_repo}:{spark_tag}")
            for ref in refs:
                subprocess.run(["docker", "rmi", ref], capture_output=True)
            logger.info(f"Removed local Docker cache images for AWS: {', '.join(refs)}")
        except Exception as e:
            logger.warning(f"Local Docker image cleanup (AWS): {e}")

    stats.print_summary()
    logger.operation_end("Teardown", args.scope, args.env, region, int(time.time() - teardown_start), ok=True)
    logger.success("Done." + (" (Shared durable remains.)" if not ((args.incl_dura or args.incl_dura_all) and args.scope == "all") else ""))


if __name__ == "__main__":
    main()
