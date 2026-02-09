
import os
import sys
import time
import json
import subprocess
import argparse
import requests

from tools import logger
from tools._env import load_dotenv, require
from tools.aws._aws_vars import get_base_vars

load_dotenv()

def get_tofu_output(stack_dir, env):
    """Retrieve output from Tofu (assumed already applied)."""
    tofu_bin = os.getenv("FRU_TF_BIN", "tofu")
    # We use -json for reliable parsing
    try:
        cmd = [tofu_bin, "output", "-json"]
        out = subprocess.check_output(cmd, cwd=stack_dir, text=True)
        return json.loads(out)
    except Exception as e:
        logger.warning(f"could not get tofu output from {stack_dir}: {e}")
        return {}

def verify_alb(alb_dns):
    logger.info(f"Checking ALB Connectivity: http://{alb_dns}")
    # Placeholder app serves a simple 200 at root
    try:
        resp = requests.get(f"http://{alb_dns}", timeout=10)
        if resp.status_code == 200:
            logger.success("ALB is UP and reachable.")
            return True
        else:
            logger.error(f"ALB returned status code: {resp.status_code}")
    except Exception as e:
        logger.error(f"ALB connection failed: {e}")
    return False

def verify_cloudwatch(env, timeout_mins=None):
    region = require("AWS_REGION")
    prefix = os.getenv("FRU_PREFIX", "fru")
    log_group = f"/fru/{env}/analytics"
    
    # Use timeout from env if not specified
    from tools._env import get_int_env
    timeout_secs = (timeout_mins * 60) if timeout_mins else get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", 300)
    
    logger.info(f"Monitoring CloudWatch Log Group: {log_group} (timeout={timeout_secs}s)")
    
    start_time = time.time()
    while (time.time() - start_time) < timeout_secs:
        try:
            # Find latest stream
            streams = subprocess.check_output([
                "aws", "logs", "describe-log-streams",
                "--log-group-name", log_group,
                "--order-by", "LastEventTime",
                "--descending",
                "--limit", "3",
                "--region", region
            ], text=True)
            
            stream_list = json.loads(streams).get("logStreams", [])
            found_success = False
            
            for s in stream_list:
                stream_name = s["logStreamName"]
                events = subprocess.check_output([
                    "aws", "logs", "get-log-events",
                    "--log-group-name", log_group,
                    "--log-stream-name", stream_name,
                    "--limit", "100",
                    "--region", region
                ], text=True)
                
                log_content = events.lower()
                if "fru bootstrap success" in log_content:
                    logger.success(f"Found success pattern in stream: {stream_name}")
                    found_success = True
                    break
                elif "fru bootstrap start" in log_content:
                    logger.info(f"... Found starting pattern in {stream_name}, still waiting for success ...")
            
            if found_success:
                return True
                
        except Exception as e:
            logger.warning(f"Waiting for logs... ({e})")
            
        time.sleep(15)
        elapsed = int(time.time() - start_time)
        logger.info(f"  [{elapsed}s] Polling for success logs...")
        
    logger.error(f"Timed out waiting for success logs after {timeout_secs}s.")
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--scope", choices=["kube", "nonkube"], default="nonkube")
    args = ap.parse_args()
    
    env = args.env
    get_base_vars(env) # ensure env vars are set for subprocesses
    
    logger.step(f"Plumbing Verification Interface (env: {env})")
    
    # 1. ALB Check
    if args.scope == "nonkube":
        stack_out = get_tofu_output("deploy-aws/nonkube", env)
        alb_dns = stack_out.get("alb_dns_name", {}).get("value")
        if alb_dns:
            verify_alb(alb_dns)
        else:
            logger.error("Could not find ALB DNS in terraform outputs.")

    # 2. CloudWatch Check
    success = verify_cloudwatch(env)
    
    if success:
        logger.success("PLUMBING VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.error("PLUMBING VERIFICATION: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
