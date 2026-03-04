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
from tools.cloud_shared.stats import DeployStats, scope_for
from tools.gcp.scope_shared.core.backend import resolve_region, resolve_state_bucket, gcs_delta_bucket
from tools.gcp.scope_shared.core.phases import PhaseTracker, deploy_phases
from tools.gcp.scope_shared.deploy.deploy_common import run_deploy_stack
from tools.gcp.kube.deploy_kube import run_deploy_kube
from tools.gcp.nonkube.deploy_nonkube import run_deploy_nonkube
from tools.cloud_shared.logging import logger

load_dotenv()


def _plan_vars_for_shared_stack(stack: str, prefix: str, gcp_proj: str, env: str, region: str) -> list[str]:
    """Build plan_vars for durable_with_cooloff, durable, or nondurable."""
    base = [f"-var=prefix={prefix}", f"-var=env={env}", f"-var=gcp_region={region}", f"-var=gcp_project_id={gcp_proj}"]
    if "nondurable" in stack:
        from tools.gcp.scope_shared.core.resource_names import artifact_registry_repo_app, artifact_registry_repo_spark
        return base + [
            f"-var=gcs_delta_bucket={gcs_delta_bucket(env, region)}",
            f"-var=artifact_registry_repo_app={artifact_registry_repo_app(env)}",
            f"-var=artifact_registry_repo_spark={artifact_registry_repo_spark(env)}",
        ]
    if "durable" in stack and "cooloff" not in stack:
        bucket = resolve_state_bucket(region)
        db_pw = os.getenv("PGPASSWORD", "postgres")
        return base + [
            f"-var=tf_state_bucket={bucket}", f"-var=tf_state_prefix={prefix}",
            f"-var=cloud_sql_root_password={db_pw}",
        ]
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    ap.add_argument("--skip-doctor", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--no-cache-build", action="store_true", help="Build images with Docker --no-cache (fixes corrupted cache)")
    ap.add_argument("--apply", action="store_true", help="Run tofu apply after plan (default: plan only)")
    ap.add_argument("--force-refresh-data", action="store_true",
                    help="Force reload DB schema and embeddings (reserved for future db_setup integration)")
    ap.add_argument("--gke-disable-deletion-protection", action="store_true",
                    help="Before kube apply: run one-off update to set deletion_protection=false on existing regional cluster (for migration to zonal)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    deploy_start = time.time()
    logger.operation_start("Deploy", args.scope, args.env, region)
    phases = deploy_phases(args.scope)
    tracker = PhaseTracker("Deploy", phases)
    stats = DeployStats()

    # Phase 1: Doctor
    tracker.start_phase(1)
    stats.set_scope("shared")
    if not args.skip_doctor:
        logger.step(f"[1/{len(phases)}] Running doctor checks...")
        with stats.timed("Doctor", "doctor checks"):
            doctor_cmd = [sys.executable, "tools/gcp/standalone/doctor.py", "--env", args.env]
            if region:
                doctor_cmd.extend(["--region", region])
            if args.skip_build:
                doctor_cmd.append("--skip-docker")
            subprocess.run(doctor_cmd, check=True, cwd=repo_root)
        logger.success("Doctor OK")
    else:
        logger.info(f"[1/{len(phases)}] Skipping doctor checks")
    tracker.end_phase(1)

    # Phase 2: Bootstrap
    tracker.start_phase(2)
    logger.step(f"[2/{len(phases)}] Bootstrapping state backend...")
    with stats.timed("Backend", "bootstrap_state_backend"):
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
        stacks.append(("infra_terraform/live_deploy/gcp/kube", 9))
    elif args.scope == "nonkube":
        stacks.append(("infra_terraform/live_deploy/gcp/nonkube", 9))
    elif args.scope == "all":
        # Match AWS: nonkube first, then kube
        stacks.append(("infra_terraform/live_deploy/gcp/nonkube", 9))
        stacks.append(("infra_terraform/live_deploy/gcp/kube", 10))

    needs_secrets_build_and_db = args.apply and args.scope in ("kube", "nonkube", "all")

    for stack, phase_idx in stacks:
        if needs_secrets_build_and_db and phase_idx >= 9:
            tracker.start_phase(6)
            stats.set_scope("shared")
            logger.step(f"[6/{len(phases)}] Ensuring secrets...")
            with stats.timed("Secrets", "ensure_secrets"):
                subprocess.run(
                    [sys.executable, "tools/gcp/scope_shared/deploy/ensure_secrets.py", "--env", args.env, "--region", region],
                    check=True,
                    cwd=repo_root,
                )
            logger.success("Secrets ensured")
            tracker.end_phase(6)
            tracker.start_phase(7)
            logger.step(f"[7/{len(phases)}] Setting up database (pgvector, schema, data)...")
            setup_db_cmd = [sys.executable, "tools/gcp/scope_shared/deploy/setup_database.py", "--env", args.env, "--region", region]
            if getattr(args, "force_refresh_data", False):
                setup_db_cmd.append("--force-refresh-data")
            with stats.timed("Database", "setup_database"):
                result = subprocess.run(
                    setup_db_cmd, check=False, cwd=repo_root,
                    env={**os.environ, "CLOUD_REGION": region},
                )
            if result.returncode != 0:
                logger.error("Database setup failed; deploy aborted (use verify-only fallback if DB was previously initialized)")
                sys.exit(result.returncode)
            logger.success("Database setup complete")
            tracker.end_phase(7)
            tracker.start_phase(8)
            if not args.skip_build:
                logger.step(f"[8/{len(phases)}] Building and pushing images...")
                build_env = {**os.environ}
                # Standardize image tagging: use shared git-based version tag (mirrors AWS).
                from tools.cloud_shared.image_tag import generate_image_tag, get_container_image_tags

                app_tag = (build_env.get("APP_IMAGE_TAG") or "").strip()
                if not app_tag or app_tag == "latest":
                    version_tag = generate_image_tag(args.env)
                    build_env["APP_IMAGE_TAG"] = version_tag
                    build_env["CONTAINER_IMAGE_TAGS"] = get_container_image_tags(version_tag)
                else:
                    build_env["CONTAINER_IMAGE_TAGS"] = app_tag

                if not (build_env.get("SPARK_IMAGE_TAG") or "").strip():
                    build_env["SPARK_IMAGE_TAG"] = "latest"
                with stats.timed("Build & push", "build_and_push_images"):
                    build_cmd = [sys.executable, "tools/gcp/scope_shared/deploy/build_and_push_images.py", "--env", args.env, "--region", region]
                    if getattr(args, "no_cache_build", False):
                        build_cmd.append("--no-cache")
                    subprocess.run(
                        build_cmd,
                        check=True,
                        cwd=repo_root,
                        env=build_env,
                    )
                logger.success("Images built and pushed")
            else:
                logger.info("Skipping build (--skip-build)")
            tracker.end_phase(8)
            needs_secrets_build_and_db = False

        phase_name = phases[phase_idx - 1]
        tracker.start_phase(phase_idx)

        if "nonkube" in stack:
            stats.set_scope(scope_for(stack))
            logger.step(f"[{phase_idx}/{len(phases)}] Init and plan {stack}...")
            ok = run_deploy_nonkube(repo_root, args.env, region, prefix, gcp_proj, args, stats=stats)
        elif "kube" in stack and "scope_shared" not in stack:
            stats.set_scope(scope_for(stack))
            logger.step(f"[{phase_idx}/{len(phases)}] Init and plan {stack}...")
            ok = run_deploy_kube(repo_root, args.env, region, prefix, gcp_proj, args, stats=stats)
        else:
            stats.set_scope(scope_for(stack))
            stack_path = os.path.join(repo_root, stack)
            if not os.path.isdir(stack_path):
                logger.warning(f"Stack dir not found: {stack_path}")
                continue
            logger.step(f"[{phase_idx}/{len(phases)}] Init and plan {stack}...")
            with stats.timed("Tofu apply", stack):
                plan_vars = _plan_vars_for_shared_stack(stack, prefix, gcp_proj, args.env, region)
                ok = run_deploy_stack(stack_path, plan_vars, region, args.env, args.apply)

        logger.success(f"{phase_name} complete")
        tracker.end_phase(phase_idx)

    deploy_dur = int(time.time() - deploy_start)
    stats.print_summary()
    logger.operation_end("Deploy", args.scope, args.env, region, deploy_dur, ok=True)
    logger.success("Deploy phases (bootstrap + plan) complete.")


if __name__ == "__main__":
    main()
