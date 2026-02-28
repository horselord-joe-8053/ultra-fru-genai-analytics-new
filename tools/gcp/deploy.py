"""
GCP Deploy Orchestrator (reference: tools/aws/deploy.py).

Usage:
  python tools/gcp/deploy.py --scope kube --env dev
  python tools/gcp/deploy.py --scope nonkube --env dev
  python tools/gcp/deploy.py --scope all --env dev

Flow:
1) doctor
2) bootstrap backend (GCS bucket)
3) apply shared durable_with_cooloff (secrets)
4) apply shared durable (VPC)
5) apply shared nondurable (buckets)
6) ensure secrets values
7) build & push images (Artifact Registry)
8) apply kube/nonkube stack

Scope "all": deploys nonkube first, then kube (matches AWS).
"""
import argparse
import os
import subprocess
import sys
import time

from tools.cloud_shared.env import load_dotenv
from tools.gcp.scope_shared.core.backend import resolve_region, resolve_state_bucket, gcs_delta_bucket
from tools.gcp.provider_config_handler import get_gke_location, get_initial_node_count
from tools.gcp.scope_shared.core.phases import PhaseTracker, deploy_phases
from tools.cloud_shared.logging import logger

load_dotenv()


def _run_gke_deletion_protection_migration(repo_root: str, env: str, region: str, prefix: str, gcp_proj: str, bucket: str) -> None:
    """One-off apply to set deletion_protection=false on existing regional GKE cluster (before migrating to zonal)."""
    stack_path = os.path.join(repo_root, "infra_terraform/live_deploy/gcp/kube")
    if not os.path.isdir(stack_path):
        return
    os.environ["FRU_ENV"] = env
    from tools.gcp.scope_shared.core.terra_init import init_stack
    from tools.gcp.scope_shared.core.terra_runner import terra
    from tools.gcp.scope_shared.deploy.deploy_common import apply_stack_with_plan

    init_stack(stack_path, env, region)
    # Untaint cluster if it was tainted by a failed apply (allows in-place update instead of replace)
    untaint = terra(["untaint", "module.gke.google_container_cluster.main"], cwd=stack_path, check=False)
    if untaint.returncode == 0:
        logger.info("Untainted GKE cluster (was tainted from previous failed apply)")

    old_cluster = f"{prefix}-gke-{env}-{region}"
    # Use initial_node_count=1 to match existing regional cluster (avoids force-replace; we only want deletion_protection update)
    old_plan_vars = [
        f"-var=prefix={prefix}", f"-var=env={env}",
        f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
        f"-var=gke_cluster_name={old_cluster}",
        f"-var=gke_location={region}",
        f"-var=initial_node_count=1",
        f"-var=gke_deletion_protection=false",
        f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
    ]
    logger.step("GKE migration: disabling deletion_protection on existing regional cluster...")
    result = terra(["plan", "-out=tfplan_migration"] + old_plan_vars, cwd=stack_path, check=False)
    if result.returncode != 0:
        logger.warning("GKE migration plan failed; skipping (cluster may already be zonal or not exist)")
        return
    apply_stack_with_plan(stack_path, old_plan_vars, region, plan_file="tfplan_migration")
    logger.success("GKE deletion_protection disabled")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--skip-doctor", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--apply", action="store_true", help="Run tofu apply after plan (default: plan only)")
    ap.add_argument("--gke-disable-deletion-protection", action="store_true",
                    help="Before kube apply: run one-off update to set deletion_protection=false on existing regional cluster (for migration to zonal)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    os.environ["GCP_REGION"] = region
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    deploy_start = time.time()
    logger.operation_start("Deploy", args.scope, args.env, region)
    phases = deploy_phases(args.scope)
    tracker = PhaseTracker("Deploy", phases)

    # Phase 1: Doctor
    tracker.start_phase(1)
    if not args.skip_doctor:
        logger.step(f"[1/{len(phases)}] Running doctor checks...")
        doctor_cmd = [sys.executable, "tools/gcp/standalone/doctor.py", "--env", args.env]
        if region:
            doctor_cmd.extend(["--region", region])
        subprocess.run(doctor_cmd, check=True, cwd=repo_root)
        logger.success("Doctor OK")
    else:
        logger.info(f"[1/{len(phases)}] Skipping doctor checks")
    tracker.end_phase(1)

    # Phase 2: Bootstrap
    tracker.start_phase(2)
    logger.step(f"[2/{len(phases)}] Bootstrapping state backend...")
    from tools.gcp.scope_shared.deploy.bootstrap_state_backend import main as bootstrap_main
    bootstrap_main()
    logger.success("Backend bootstrapped")
    tracker.end_phase(2)

    prefix = os.getenv("PROJ_PREFIX", "").strip() or os.getenv("FRU_PREFIX", "fru")
    gcp_proj = os.getenv("GCP_PROJECT_ID", "")

    # Phases 3–6: durable_with_cooloff, durable, nondurable, kube/nonkube
    stacks = [
        ("infra_terraform/live_deploy/gcp/scope_shared/durable_with_cooloff", 3),
        ("infra_terraform/live_deploy/gcp/scope_shared/durable", 4),
        ("infra_terraform/live_deploy/gcp/scope_shared/nondurable", 5),
    ]
    if args.scope == "kube":
        stacks.append(("infra_terraform/live_deploy/gcp/kube", 8))
    elif args.scope == "nonkube":
        stacks.append(("infra_terraform/live_deploy/gcp/nonkube", 8))
    elif args.scope == "all":
        # Match AWS: nonkube first, then kube
        stacks.append(("infra_terraform/live_deploy/gcp/nonkube", 8))
        stacks.append(("infra_terraform/live_deploy/gcp/kube", 9))

    needs_secrets_and_build = args.apply and args.scope in ("kube", "nonkube", "all")

    for stack, phase_idx in stacks:
        if needs_secrets_and_build and phase_idx >= 8:
            tracker.start_phase(6)
            logger.step(f"[6/{len(phases)}] Ensuring secrets...")
            subprocess.run(
                [sys.executable, "tools/gcp/scope_shared/deploy/ensure_secrets.py", "--env", args.env, "--region", region],
                check=True,
                cwd=repo_root,
            )
            logger.success("Secrets ensured")
            tracker.end_phase(6)
            tracker.start_phase(7)
            if not args.skip_build:
                logger.step(f"[7/{len(phases)}] Building and pushing images...")
                build_env = {**os.environ}
                if not build_env.get("APP_IMAGE_TAG"):
                    build_env["APP_IMAGE_TAG"] = "latest"
                if not build_env.get("SPARK_IMAGE_TAG"):
                    build_env["SPARK_IMAGE_TAG"] = "latest"
                subprocess.run(
                    [sys.executable, "tools/gcp/scope_shared/deploy/build_and_push_images.py", "--env", args.env, "--region", region],
                    check=True,
                    cwd=repo_root,
                    env=build_env,
                )
                logger.success("Images built and pushed")
            else:
                logger.info("Skipping build (--skip-build)")
            tracker.end_phase(7)
            needs_secrets_and_build = False

        stack_path = os.path.join(repo_root, stack)
        if not os.path.isdir(stack_path):
            logger.warning(f"Stack dir not found: {stack_path}")
            continue
        tracker.start_phase(phase_idx)
        phase_name = phases[phase_idx - 1]
        logger.step(f"[{phase_idx}/{len(phases)}] Init and plan {stack}...")
        from tools.gcp.scope_shared.core.terra_init import init_stack
        from tools.gcp.scope_shared.core.terra_runner import terra
        init_stack(stack_path, args.env, region)
        if "nondurable" in stack:
            from tools.gcp.scope_shared.core.resource_names import artifact_registry_repo_app, artifact_registry_repo_spark
            plan_vars = [
                f"-var=prefix={prefix}", f"-var=env={args.env}",
                f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
                f"-var=gcs_delta_bucket={gcs_delta_bucket(args.env, region)}",
                f"-var=artifact_registry_repo_app={artifact_registry_repo_app(args.env)}",
                f"-var=artifact_registry_repo_spark={artifact_registry_repo_spark(args.env)}",
            ]
        elif "nonkube" in stack:
            from tools.gcp.scope_shared.core.backend import resolve_state_bucket
            from tools.gcp.scope_shared.core.resource_names import (
                cloud_run_service,
                spark_job_name,
                artifact_registry_repo_app,
                artifact_registry_repo_spark,
            )
            bucket = resolve_state_bucket(region)
            delta_bucket = gcs_delta_bucket(args.env, region)
            repo_app = artifact_registry_repo_app(args.env)
            repo_spark = artifact_registry_repo_spark(args.env)
            # When skip-build, use public placeholder. Otherwise use app/spark images (Artifact Registry: REPO/IMAGE:TAG)
            _placeholder = "gcr.io/google-samples/hello-app:1.0"
            app_img = os.getenv("TF_VAR_app_image") or (
                _placeholder if args.skip_build else f"{region}-docker.pkg.dev/{gcp_proj}/{repo_app}/app:latest"
            )
            spark_img = os.getenv("TF_VAR_spark_image") or (
                _placeholder if args.skip_build else f"{region}-docker.pkg.dev/{gcp_proj}/{repo_spark}/spark:latest"
            )
            plan_vars = [
                f"-var=prefix={prefix}", f"-var=env={args.env}",
                f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
                f"-var=cloud_run_service_name={cloud_run_service(args.env, region)}",
                f"-var=spark_job_name={spark_job_name(args.env, region)}",
                f"-var=app_image={app_img}", f"-var=spark_image={spark_img}",
                f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
                f"-var=delta_bucket_fallback={delta_bucket}",
            ]
        elif "kube" in stack and "scope_shared" not in stack and "nonkube" not in stack:
            from tools.gcp.scope_shared.core.backend import resolve_state_bucket
            from tools.gcp.scope_shared.core.resource_names import gke_cluster
            bucket = resolve_state_bucket(region)
            gke_location = get_gke_location(region)
            zone = gke_location if gke_location != region else None
            initial_node_count = get_initial_node_count(region)
            # Migration: if moving from regional to zonal, first disable deletion_protection on existing cluster
            if args.apply and args.gke_disable_deletion_protection and zone:
                _run_gke_deletion_protection_migration(repo_root, args.env, region, prefix, gcp_proj, bucket)
            plan_vars = [
                f"-var=prefix={prefix}", f"-var=env={args.env}",
                f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
                f"-var=gke_cluster_name={gke_cluster(args.env, region, zone=zone)}",
                f"-var=gke_location={gke_location}",
                f"-var=initial_node_count={initial_node_count}",
                f"-var=gke_deletion_protection=false",
                f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
            ]
        elif "durable" in stack and "cooloff" not in stack:
            from tools.gcp.scope_shared.core.backend import resolve_state_bucket
            bucket = resolve_state_bucket(region)
            db_pw = os.getenv("PGPASSWORD", "postgres")
            plan_vars = [
                f"-var=prefix={prefix}", f"-var=env={args.env}",
                f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
                f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
                f"-var=cloud_sql_root_password={db_pw}",
            ]
        else:
            plan_vars = [
                f"-var=prefix={prefix}", f"-var=env={args.env}",
                f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}",
            ]
        result = terra(["plan", "-out=tfplan"] + plan_vars, cwd=stack_path, check=False)
        if args.apply and result.returncode == 0:
            logger.step(f"[{phase_idx}/{len(phases)}] Applying {stack}...")
            from tools.gcp.scope_shared.deploy.deploy_common import apply_stack_with_plan
            apply_stack_with_plan(stack_path, plan_vars, region)
        logger.success(f"{phase_name} complete")
        tracker.end_phase(phase_idx)

    deploy_dur = int(time.time() - deploy_start)
    logger.operation_end("Deploy", args.scope, args.env, region, deploy_dur, ok=True)
    logger.success("Deploy phases (bootstrap + plan) complete.")


if __name__ == "__main__":
    main()
