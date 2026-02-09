import os
import argparse
import sys
import subprocess
from tools import logger

def run_command(cmd, cwd=None):
    """Run a subprocess command and exit with its return code."""
    try:
        # Pass through the current environment with the virtualenv active
        env = os.environ.copy()
        
        # Ensure the project root (where orchestrator.py lives) is in PYTHONPATH
        project_root = os.getcwd()
        env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
        
        # Bypass dotfile permission issues by using a non-dot directory for Terraform data
        env["TF_DATA_DIR"] = "tofu_data"

        # If we are in the orchestrator, we might assume the python executable 
        # is the one running this script (if run via venv) or we explicitly call python.
        # We'll use sys.executable to ensure we use the same python interpreter.
        if cmd[0] == "python":
            cmd[0] = sys.executable

        logger.info(f"--> Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, env=env)
        if result.returncode != 0:
            sys.exit(result.returncode)
    except Exception as e:
        logger.error(f"Error running command: {e}")
        sys.exit(1)

def handle_aws(args):
    """Route commands to AWS tools."""
    base_path = "tools/aws"
    
    cmd_args = []
    if args.env:
        cmd_args.extend(["--env", args.env])
    
    if args.command == "doctor":
        script = f"{base_path}/doctor.py"
        with logger.Heartbeat("Preflight checks"):
            run_command(["python", script] + cmd_args)
        
    elif args.command == "deploy":
        if not args.scope:
            logger.error("Error: --scope required for deploy")
            sys.exit(1)
        script = f"{base_path}/deploy.py"
        cmd_args.extend(["--scope", args.scope])
        if args.skip_doctor:
            cmd_args.append("--skip-doctor")
        with logger.Heartbeat(f"Deployment scope={args.scope} env={args.env}"):
            run_command(["python", script] + cmd_args)
        
        # Auto-verify after successful deploy
        logger.step("Initiating automatic plumbing verification...")
        verify_script = f"{base_path}/verify_plumbing.py"
        run_command(["python", verify_script] + cmd_args)
        
    elif args.command == "teardown":
        if not args.scope:
            logger.error("Error: --scope required for teardown")
            sys.exit(1)
        script = f"{base_path}/teardown.py"
        cmd_args.extend(["--scope", args.scope])
        
        # Translate --force to --non-interactive for compatibility if user habitually uses force
        if args.non_interactive or args.force:
            cmd_args.append("--non-interactive")
            
        with logger.Heartbeat(f"Teardown scope={args.scope} env={args.env}"):
            run_command(["python", script] + cmd_args)
        
    elif args.command == "verify":
        if not args.scope:
            logger.error("Error: --scope required for verify")
            sys.exit(1)
        script = f"{base_path}/verify_plumbing.py"
        cmd_args.extend(["--scope", args.scope])
        # verify_plumbing.py itself polls, so we wrap it here for a top-level heartbeat
        with logger.Heartbeat(f"Plumbing verification scope={args.scope} env={args.env}"):
            run_command(["python", script] + cmd_args)
        
    else:
        logger.error(f"Unknown command for AWS: {args.command}")
        sys.exit(1)

def handle_gcp(args):
    """Route commands to GCP tools."""
    print("GCP provider implementation is pending.")
    sys.exit(1)

def handle_local(args):
    """Route commands to Local tools."""
    print("Local provider implementation is pending.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Unified Orchestrator for FRU GenAI Analytics")
    
    # Core arguments
    parser.add_argument("command", choices=["deploy", "teardown", "doctor", "verify"], help="Action to perform")
    parser.add_argument("--provider", choices=["aws", "gcp", "local"], default="aws", help="Target infrastructure provider")
    
    # Passthrough arguments (common across providers)
    parser.add_argument("--scope", choices=["kube", "nonkube", "all"], help="Scope of operation (deployment targets)")
    parser.add_argument("--env", help="Environment (dev, prod, etc.)")
    parser.add_argument("--non-interactive", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--force", action="store_true", help="Legacy alias for --non-interactive")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip preflight checks (deploy only)")

    # Parse args
    args = parser.parse_args()

    # Routing
    if args.provider == "aws":
        handle_aws(args)
    elif args.provider == "gcp":
        handle_gcp(args)
    elif args.provider == "local":
        handle_local(args)

if __name__ == "__main__":
    main()
