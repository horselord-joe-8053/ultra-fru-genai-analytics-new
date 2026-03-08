"""
Unified Orchestrator for deploy, teardown, doctor, verify.

Supports multiple cloud providers (AWS, GCP) and multiple regions per provider.
Routes commands to provider-specific tools under tools/{aws,gcp}/.

Usage (from project root, with venv):

  # AWS (default provider)
  .venv/bin/python orchestrator.py deploy --provider aws --scope all --env dev
  .venv/bin/python orchestrator.py deploy --provider aws --scope all --env dev --cloud-region us-east-1
  .venv/bin/python orchestrator.py verify --provider aws --scope all --env dev

  # GCP
  .venv/bin/python orchestrator.py deploy --provider gcp --scope all --env dev
  .venv/bin/python orchestrator.py deploy --provider gcp --scope all --env dev --cloud-region us-central1
  .venv/bin/python orchestrator.py verify --provider gcp --scope all --env dev

  # Local (PostgreSQL + Spark via Docker; no --scope/--env/--cloud-region)
  .venv/bin/python orchestrator.py deploy --provider local   # deploy + start API/frontend + verify (default)
  .venv/bin/python orchestrator.py deploy --provider local --no-start-local   # deploy only
  .venv/bin/python orchestrator.py deploy --provider local --shutdown-local   # terminate local API and frontend only
  .venv/bin/python orchestrator.py teardown --provider local
  .venv/bin/python orchestrator.py doctor --provider local
  .venv/bin/python orchestrator.py verify --provider local

  # Doctor (preflight checks) – any provider
  .venv/bin/python orchestrator.py doctor --provider gcp --env dev --cloud-region us-central1

  # Teardown – any provider
  .venv/bin/python orchestrator.py teardown --provider gcp --scope all --env dev --non-interactive

Environment:
  FRU_ENV, CLOUD_REGION, GCP_PROJECT_ID, etc. from .env.
  --cloud-region overrides CLOUD_REGION when set.

No PYTHONPATH=. needed: orchestrator sets it for subprocesses.
Deploy runs 'pip install -r requirements.txt' first (use --skip-ensure-deps to skip).
"""
import os
import argparse
import sys
import subprocess
from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, get_int_env

load_dotenv()

def run_command(cmd, cwd=None, force_no_timeout: bool = False):
    """Run a subprocess command and exit with its return code.
    Respects LOGGING_TASK_DEFAULT_TIMEOUT: when set > 0, kills the child after that many seconds.
    Use force_no_timeout=True for teardown (can take 60+ min for EKS/Aurora/VPC).
    """
    try:
        # Pass through the current environment with the virtualenv active
        env = os.environ.copy()
        
        # Ensure the project root (where orchestrator.py lives) is in PYTHONPATH
        project_root = os.getcwd()
        env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
        
        # Single shared OpenTofu data dir (providers, etc.) for all stacks; absolute path
        env["TF_DATA_DIR"] = os.path.abspath(os.path.join(project_root, "tofu_data"))

        # Unbuffered stdout so child output (heartbeats, etc.) appears immediately
        env["PYTHONUNBUFFERED"] = "1"

        # If we are in the orchestrator, we might assume the python executable 
        # is the one running this script (if run via venv) or we explicitly call python.
        # We'll use sys.executable to ensure we use the same python interpreter.
        if cmd[0] == "python":
            cmd[0] = sys.executable

        timeout = 0 if force_no_timeout else get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", 0)  # 0 = no timeout
        if timeout > 0:
            logger.info(f"--> Running: {' '.join(cmd)} (timeout: {timeout}s)")
        else:
            logger.info(f"--> Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout if timeout > 0 else None)
        if result.returncode != 0:
            sys.exit(result.returncode)
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {e.timeout}s: {' '.join(e.cmd)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running command: {e}")
        sys.exit(1)

def ensure_deps():
    """Install deps from requirements.txt so venv is ready. Idempotent; fast when already satisfied."""
    req_file = os.path.join(os.getcwd(), "requirements.txt")
    if os.path.exists(req_file):
        logger.info("Ensuring dependencies (pip install -r requirements.txt)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
            check=True,
            cwd=os.getcwd(),
        )

def _handle_provider(args, base_path: str, provider: str, deploy_extra_before: list[str] | None = None):
    """Unified provider handler. Routes doctor, deploy, teardown, verify to provider-specific tools."""
    deploy_extra_before = deploy_extra_before or []

    cmd_args = []
    if args.env:
        cmd_args.extend(["--env", args.env])
    if args.cloud_region:
        cmd_args.extend(["--region", args.cloud_region])

    if args.command == "doctor":
        script = f"{base_path}/standalone/doctor.py"
        with logger.Heartbeat("Preflight checks"):
            run_command(["python", script] + cmd_args)

    elif args.command == "deploy":
        if not args.scope:
            logger.error("Error: --scope required for deploy")
            sys.exit(1)
        if not args.skip_ensure_deps:
            ensure_deps()

        if args.preempt:
            logger.step("Executing Preempt Sequence: Teardown -> Verify Teardown -> Deploy -> Verify Deploy")
            teardown_script = f"{base_path}/teardown.py"
            teardown_args = cmd_args + ["--non-interactive", "--scope", args.scope]
            if args.incl_dura_all:
                teardown_args.append("--incl-dura-all")
            elif args.incl_dura:
                teardown_args.append("--incl-dura")
            with logger.Heartbeat(f"Preempt Teardown scope={args.scope} env={args.env}", timeout=-1):
                run_command(["python", teardown_script] + teardown_args, force_no_timeout=True)
            verify_teardown_script = f"{base_path}/scope_shared/verify/verify_all_teardown.py"
            run_command(["python", verify_teardown_script] + cmd_args + ["--scope", args.scope])

        script = f"{base_path}/deploy.py"
        deploy_args = ["python", script] + deploy_extra_before + ["--scope", args.scope] + cmd_args
        if args.skip_doctor:
            deploy_args.append("--skip-doctor")
        if args.skip_build:
            deploy_args.append("--skip-build")
        if getattr(args, "force_build", False):
            deploy_args.append("--force-build")
        if getattr(args, "force_refresh_data", False):
            deploy_args.append("--force-refresh-data")
        if getattr(args, "elb", False):
            deploy_args.append("--elb")
        if getattr(args, "gke_disable_deletion_protection", False):
            deploy_args.append("--gke-disable-deletion-protection")

        with logger.Heartbeat(f"Deployment scope={args.scope} env={args.env}", timeout=-1):
            run_command(deploy_args, force_no_timeout=True)

        logger.step("Initiating automatic verification...")
        verify_script = f"{base_path}/scope_shared/verify/verify_all_deploy.py"
        verify_args = cmd_args + ["--scope", args.scope]
        run_command(["python", verify_script] + verify_args)

    elif args.command == "teardown":
        if not args.scope:
            logger.error("Error: --scope required for teardown")
            sys.exit(1)
        script = f"{base_path}/teardown.py"
        cmd_args.extend(["--scope", args.scope])
        if args.incl_dura_all:
            cmd_args.append("--incl-dura-all")
        elif args.incl_dura:
            cmd_args.append("--incl-dura")
        if args.non_interactive or args.force:
            cmd_args.append("--non-interactive")

        hb_msg = f"Teardown scope={args.scope} env={args.env}"
        if args.cloud_region:
            hb_msg += f" region={args.cloud_region}"
        with logger.Heartbeat(hb_msg, timeout=-1):
            run_command(["python", script] + cmd_args, force_no_timeout=True)
        logger.step("Verifying teardown...")
        verify_teardown_script = f"{base_path}/scope_shared/verify/verify_all_teardown.py"
        run_command(["python", verify_teardown_script] + cmd_args)

    elif args.command == "verify":
        if not args.scope:
            logger.error("Error: --scope required for verify")
            sys.exit(1)
        script = f"{base_path}/scope_shared/verify/verify_all_deploy.py"
        cmd_args.extend(["--scope", args.scope])
        with logger.Heartbeat(f"Verification scope={args.scope} env={args.env}"):
            run_command(["python", script] + cmd_args)

    else:
        logger.error(f"Unknown command for {provider}: {args.command}")
        sys.exit(1)


def handle_aws(args):
    """Route commands to AWS tools (tools/aws/*). Supports --cloud-region for multi-region."""
    _handle_provider(args, "tools/aws", "aws", deploy_extra_before=[])


def handle_gcp(args):
    """Route commands to GCP tools (tools/gcp/*). Supports --cloud-region for multi-region."""
    _handle_provider(args, "tools/gcp", "gcp", deploy_extra_before=["--apply"])

def handle_local(args):
    """Route commands to Local tools (PostgreSQL + Spark via Docker).
    --start-local: deploy + start API/frontend + verify (default for deploy).
    --shutdown-local: terminate local API and frontend only; or run before deploy for clean slate.
    --no-start-local: deploy only, do not start or verify.
    """
    base_path = "tools/local"
    project_root = os.getcwd()

    if args.command == "doctor":
        script = f"{base_path}/standalone/doctor.py"
        with logger.Heartbeat("Local preflight"):
            run_command(["python", script])

    elif args.command == "deploy":
        # --shutdown-local only (no --start-local): terminate API/frontend and exit
        if getattr(args, "shutdown_local", False) and not getattr(args, "start_local", False):
            logger.step("Shutting down local API and frontend")
            run_command(["python", f"{base_path}/shutdown_local.py"])
            return

        if not args.skip_ensure_deps:
            ensure_deps()
        if not args.skip_doctor:
            run_command(["python", f"{base_path}/standalone/doctor.py"])

        # --shutdown-local with --start-local: clean slate before deploy
        if getattr(args, "shutdown_local", False):
            logger.step("Shutting down local API and frontend (clean slate)")
            run_command(["python", f"{base_path}/shutdown_local.py"])

        script = f"{base_path}/deploy.py"
        do_start = not getattr(args, "no_start_local", False)

        # Wrap deploy + start + verify in one Heartbeat so it exits when the flow completes.
        # Local deploy (Spark) can take 10+ min; use timeout=-1 to avoid heartbeat timeout.
        # AWS/GCP use deploy-only Heartbeat; local differs because start+verify run in-process.
        with logger.Heartbeat("Local deploy", timeout=-1):
            run_command(["python", script], force_no_timeout=True)
            if do_start:
                logger.step("Starting local API and frontend")
                run_command(["python", f"{base_path}/start_local.py"])
                logger.step("Verifying local deployment")
                run_command(["python", f"{base_path}/scope_shared/verify/verify_all_deploy.py"])

        if not do_start:
            logger.step("Local deploy complete. Start API and frontend to verify:")
            logger.info("  python orchestrator.py deploy --provider local --start-local")
            logger.info("  Or: PORT=5001 PYTHONPATH=core_app python -m backend.api.app")
            logger.info("  And: cd core_app/frontend && npm run dev")

    elif args.command == "teardown":
        script = f"{base_path}/teardown.py"
        logger.step("Shutting down local API and frontend")
        run_command(["python", f"{base_path}/shutdown_local.py"])
        with logger.Heartbeat("Local teardown"):
            run_command(["python", script])
        logger.step("Verifying teardown...")
        run_command(["python", f"{base_path}/scope_shared/verify/verify_all_teardown.py"])

    elif args.command == "verify":
        script = f"{base_path}/scope_shared/verify/verify_all_deploy.py"
        with logger.Heartbeat("Local verify (API must be running on localhost:5001)"):
            run_command(["python", script])

    else:
        logger.error(f"Unknown command for local: {args.command}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Unified Orchestrator for FRU GenAI Analytics. Supports AWS and GCP across multiple regions."
    )

    # Core arguments
    parser.add_argument("command", choices=["deploy", "teardown", "doctor", "verify"], help="Action to perform")
    parser.add_argument(
        "--provider",
        choices=["aws", "gcp", "local"],
        default="aws",
        help="Target cloud provider (aws, gcp, or local; local is pending)",
    )
    
    # Passthrough arguments (common across providers)
    parser.add_argument("--scope", choices=["kube", "nonkube", "all"], help="Scope of operation (deployment targets)")
    parser.add_argument("--env", default=os.getenv("FRU_ENV", "dev"), help="Environment (dev, prod, etc.)")
    parser.add_argument(
        "--cloud-region",
        default=None,
        help="Cloud region (e.g. us-east-1, us-central1). Default: CLOUD_REGION from .env. Passed as --region to child scripts.",
    )
    parser.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--force", action="store_true", help="Legacy alias for --non-interactive")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip preflight checks (deploy only)")
    parser.add_argument("--skip-ensure-deps", action="store_true", help="Skip pip install -r requirements.txt (deploy only)")
    parser.add_argument("--skip-build", action="store_true", help="Skip build; use repo:latest from ECR (deploy only)")
    parser.add_argument("--force-build", action="store_true", help="Force build even when content hash matches (deploy only)")
    parser.add_argument("--force-refresh-data", action="store_true",
                        help="Force reload DB schema and embeddings (deploy only; drops and repopulates fru_sales_embeddings)")
    parser.add_argument("--elb", action="store_true", help="[Kube only] Use in-tree Classic ELB instead of NLB (deploy only)")
    parser.add_argument("--preempt", action="store_true", help="Run full teardown and verification before deploy")
    parser.add_argument("--incl-dura", action="store_true", help="Include durable (VPC+Aurora) in teardown; secrets remain (scope=all only)")
    parser.add_argument("--incl-dura-all", action="store_true", help="Include durable and durable_with_cooloff (secrets); full teardown (scope=all only)")
    parser.add_argument("--gke-disable-deletion-protection", action="store_true",
                        help="[GCP] Before kube apply: disable deletion_protection on existing regional cluster (for migration to zonal)")

    # Local-only flags (used when --provider local)
    parser.add_argument("--start-local", action="store_true",
                        help="[Local] After deploy: start API and frontend, then verify. Default for deploy --provider local.")
    parser.add_argument("--shutdown-local", action="store_true",
                        help="[Local] Terminate local API and frontend only (no deploy/teardown). Or run before deploy for clean slate.")
    parser.add_argument("--no-start-local", action="store_true",
                        help="[Local] Deploy only; do not start API/frontend or verify.")

    # Parse args
    args = parser.parse_args()

    # Set CLOUD_PROVIDER so core_app and child scripts use the chosen provider
    os.environ["CLOUD_PROVIDER"] = args.provider

    # Route to provider-specific handlers (tools/aws/* or tools/gcp/*)
    if args.provider == "aws":
        handle_aws(args)
    elif args.provider == "gcp":
        handle_gcp(args)
    elif args.provider == "local":
        handle_local(args)

if __name__ == "__main__":
    main()
