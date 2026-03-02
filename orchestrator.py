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

def handle_aws(args):
    """Route commands to AWS tools (tools/aws/*). Supports --cloud-region for multi-region."""
    base_path = "tools/aws"
    
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
            
        # Preempt logic: Teardown -> Verify Teardown
        if args.preempt:
            logger.step("Executing Preempt Sequence: Teardown -> Verify Teardown -> Deploy -> Verify Deploy")
            
            # 1. Teardown
            teardown_script = f"{base_path}/teardown.py"
            # Ensure non-interactive for preempt
            teardown_args = cmd_args + ["--non-interactive", "--scope", args.scope]
            if args.incl_dura_all:
                teardown_args.append("--incl-dura-all")
            elif args.incl_dura:
                teardown_args.append("--incl-dura")
            with logger.Heartbeat(f"Preempt Teardown scope={args.scope} env={args.env}", timeout=-1):
                run_command(["python", teardown_script] + teardown_args, force_no_timeout=True)
                
            # 2. Verify Teardown
            verify_teardown_script = f"{base_path}/scope_shared/verify/verify_all_teardown.py"
            run_command(["python", verify_teardown_script] + cmd_args + ["--scope", args.scope])
            
        # 3. Deploy
        script = f"{base_path}/deploy.py"
        deploy_args = cmd_args + ["--scope", args.scope]
        if args.skip_doctor:
            deploy_args.append("--skip-doctor")
        if args.skip_build:
            deploy_args.append("--skip-build")
        if args.force_build:
            deploy_args.append("--force-build")
        if args.force_refresh_data:
            deploy_args.append("--force-refresh-data")
        if args.elb:
            deploy_args.append("--elb")
            
        with logger.Heartbeat(f"Deployment scope={args.scope} env={args.env}"):
            run_command(["python", script] + deploy_args)
        
        # 4. Auto-verify after successful deploy (Verify Deploy)
        logger.step("Initiating automatic verification...")
        verify_script = f"{base_path}/scope_shared/verify/verify_all_deploy.py"
        verify_args = cmd_args + ["--scope", args.scope]  # verify does not accept --skip-doctor
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
        # Translate --force to --non-interactive for compatibility if user habitually uses force
        if args.non_interactive or args.force:
            cmd_args.append("--non-interactive")
            
        hb_msg = f"Teardown scope={args.scope} env={args.env}"
        if args.cloud_region:
            hb_msg += f" region={args.cloud_region}"
        with logger.Heartbeat(hb_msg, timeout=-1):  # Teardown can take 60+ min; -1 = no timeout
            run_command(["python", script] + cmd_args, force_no_timeout=True)
        # Verify teardown: confirm resources are gone (namespace, ECS cluster, etc.)
        logger.step("Verifying teardown...")
        verify_teardown_script = f"{base_path}/scope_shared/verify/verify_all_teardown.py"
        run_command(["python", verify_teardown_script] + cmd_args)
        
    elif args.command == "verify":
        if not args.scope:
            logger.error("Error: --scope required for verify")
            sys.exit(1)
        script = f"{base_path}/scope_shared/verify/verify_all_deploy.py"
        cmd_args.extend(["--scope", args.scope])
        # verify_all_deploy.py itself polls, so we wrap it here for a top-level heartbeat
        with logger.Heartbeat(f"Verification scope={args.scope} env={args.env}"):
            run_command(["python", script] + cmd_args)
        
    else:
        logger.error(f"Unknown command for AWS: {args.command}")
        sys.exit(1)

def handle_gcp(args):
    """Route commands to GCP tools (tools/gcp/*). Supports --cloud-region for multi-region."""
    base_path = "tools/gcp"
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
        # Preempt: Teardown -> Verify Teardown -> Deploy -> Verify (reference: AWS handle_aws)
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
        deploy_args = ["python", script, "--scope", args.scope, "--apply"] + cmd_args
        if args.skip_doctor:
            deploy_args.append("--skip-doctor")
        if args.skip_build:
            deploy_args.append("--skip-build")
        if getattr(args, "force_refresh_data", False):
            deploy_args.append("--force-refresh-data")
        if getattr(args, "gke_disable_deletion_protection", False):
            deploy_args.append("--gke-disable-deletion-protection")
        with logger.Heartbeat(f"Deployment scope={args.scope} env={args.env}"):
            run_command(deploy_args)
        # Auto-verify after deploy (matches AWS)
        logger.step("Initiating automatic verification...")
        run_command(["python", f"{base_path}/scope_shared/verify/verify_all_deploy.py"] + cmd_args + ["--scope", args.scope])
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
        with logger.Heartbeat(f"Teardown scope={args.scope} env={args.env}", timeout=-1):
            run_command(["python", script] + cmd_args, force_no_timeout=True)
        # Verify teardown: confirm Cloud Run / GKE resources are gone
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
        logger.error(f"Unknown command for GCP: {args.command}")
        sys.exit(1)

def handle_local(args):
    """Route commands to Local tools. Implementation pending."""
    print("Local provider implementation is pending.")
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
