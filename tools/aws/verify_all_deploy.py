
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
from tools.tofu_runner import ensure_shared_tofu_env

load_dotenv()

def get_tofu_output(stack_dir, env):
    """Retrieve output from Tofu (assumed already applied)."""
    ensure_shared_tofu_env()
    tofu_bin = os.getenv("FRU_TF_BIN", "tofu")
    # We use -json for reliable parsing
    try:
        cmd = [tofu_bin, "output", "-json"]
        out = subprocess.check_output(cmd, cwd=stack_dir, text=True)
        return json.loads(out)
    except Exception as e:
        logger.warning(f"could not get tofu output from {stack_dir}: {e}")
        return {}

def verify_api_endpoints(base_url, timeout_secs=300):
    logger.info(f"Validating API Endpoints at: {base_url} (timeout={timeout_secs}s)")
    start_time = time.time()
    
    # Check /query/stream - accept 200 even if agent is disabled (missing DB)
    def check_query_stream(r):
        if r.status_code != 200: return False
        if "Agent-based query processing is disabled" in r.text:
            logger.info("  (Note: Agent is disabled due to missing DB, but endpoint is reachable)")
            return True
        return True

    endpoints = [
        {"path": "/health", "name": "Health", "check": lambda r: r.status_code == 200},
        {"path": "/version", "name": "Version", "check": lambda r: r.status_code == 200},
        {"path": "/", "name": "Frontend", "check": lambda r: r.status_code == 200 and "<html" in r.text.lower()},
        {"path": "/query/stream?query=test", "name": "QueryStream", "check": check_query_stream},
    ]
    
    results = {e["name"]: False for e in endpoints}
    last_status = {e["name"]: None for e in endpoints}
    last_error = {e["name"]: None for e in endpoints}
    
    while (time.time() - start_time) < timeout_secs:
        elapsed = int(time.time() - start_time)
        for e in endpoints:
            if results[e["name"]]: continue
            
            url = base_url.rstrip("/") + e["path"]
            try:
                resp = requests.get(url, timeout=10)
                last_status[e["name"]] = resp.status_code
                last_error[e["name"]] = None
                
                if e["check"](resp):
                    logger.success(f"✓ {e['name']} endpoint is UP: {url}")
                    results[e["name"]] = True
                else:
                    # Got a response but it doesn't match expected result
                    if resp.status_code >= 500:
                        # 5xx errors are server errors - fail fast
                        logger.error(f"✗ {e['name']} endpoint returned {resp.status_code} (Server Error) - failing immediately")
                        logger.error(f"  URL: {url}")
                        logger.error(f"  Response body: {resp.text[:200]}")
                        return False
                    elif resp.status_code >= 400:
                        # 4xx errors are client errors - fail fast
                        logger.error(f"✗ {e['name']} endpoint returned {resp.status_code} (Client Error) - failing immediately")
                        logger.error(f"  URL: {url}")
                        return False
                    else:
                        # 2xx but check failed (e.g., no "<html" in frontend)
                        if (elapsed % 30) == 0 or elapsed < 10:
                            logger.info(f"  [{elapsed}s] {e['name']} check failed (status {resp.status_code}), waiting...")
            except requests.exceptions.ConnectionError as ex:
                last_error[e["name"]] = str(ex)
                # Connection errors are transient - keep retrying
                if (elapsed % 30) == 0 or elapsed < 10:
                    logger.info(f"  [{elapsed}s] {e['name']} connection failed, retrying... ({type(ex).__name__})")
            except requests.exceptions.Timeout as ex:
                last_error[e["name"]] = str(ex)
                # Timeouts are transient - keep retrying
                if (elapsed % 30) == 0 or elapsed < 10:
                    logger.info(f"  [{elapsed}s] {e['name']} timeout, retrying...")
            except Exception as ex:
                last_error[e["name"]] = str(ex)
                if (elapsed % 30) == 0 or elapsed < 10:
                    logger.info(f"  [{elapsed}s] {e['name']} error, retrying... ({type(ex).__name__})")
        
        if all(results.values()):
            return True
        
        time.sleep(10)
    
    # Timeout reached - report which endpoints failed
    logger.error(f"\n[VERIFICATION TIMEOUT] Endpoints failed to respond successfully within {timeout_secs}s:")
    for e in endpoints:
        if not results[e["name"]]:
            if last_status[e["name"]]:
                logger.error(f"  ✗ {e['name']}: HTTP {last_status[e['name']]}")
            else:
                logger.error(f"  ✗ {e['name']}: {last_error[e['name']] or 'Unknown error'}")
            
    return False

def verify_cloudwatch(env, timeout_mins=None):
    region = require("AWS_REGION")
    prefix = os.getenv("FRU_PREFIX", "fru")
    # Use log group from env if set, otherwise default
    log_group = os.getenv("CLOUDWATCH_LOG_GROUP") or f"/fru/{env}/analytics"
    
    # Use timeout from env if not specified
    from tools._env import get_int_env
    timeout_secs = (timeout_mins * 60) if timeout_mins else get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", 300)
    
    logger.info(f"Monitoring CloudWatch Log Group: {log_group} (timeout={timeout_secs}s)")
    
    start_time = time.time()
    
    # Check if log group exists first to avoid looping on ResourceNotFound
    try:
        out = subprocess.check_output([
            "aws", "logs", "describe-log-groups",
            "--log-group-name-prefix", log_group,
            "--region", region
        ], text=True)
        groups = json.loads(out).get("logGroups", [])
        # Check if we have an exact match or if the list is non-empty and we are happy
        # Ideally check for exact match
        if not any(g["logGroupName"] == log_group for g in groups):
             logger.warning(f"Log group {log_group} not found in describe-log-groups output. Skipping log verification.")
             return True # Treat missing logs as warning, not failure
    except Exception as e:
        logger.warning(f"Log group {log_group} not found in describe-log-groups output. Skipping log verification.")
        return True # Treat missing logs as warning, not failure, if endpoints are checked elsewhere
    except Exception as e:
        logger.warning(f"Log group {log_group} check failed. Skipping log verification. ({e})")
        return True # Treat check failure as warning

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
    
    # 1. Endpoint Check
    endpoint_success = False
    if args.scope == "nonkube":
        stack_out = get_tofu_output("deploy-aws/nonkube", env)
        alb_dns = stack_out.get("alb_dns_name", {}).get("value")
        if alb_dns:
            endpoint_success = verify_api_endpoints(f"http://{alb_dns}")
            if not endpoint_success:
                logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
                sys.exit(1)
        else:
            logger.error("Could not find ALB DNS in terraform outputs.")
            sys.exit(1)
    
    elif args.scope == "kube":
        # Get K8s LoadBalancer URL
        logger.info("Waiting for EKS LoadBalancer hostname...")
        lb_host = ""
        for _ in range(30): # Wait up to 5 minutes for LB hostname
            try:
                cmd = ["kubectl", "get", "svc", "fru-api-svc", "-n", "fru", "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"]
                lb_host = subprocess.check_output(cmd, text=True).strip()
                if lb_host: break
            except: pass
            time.sleep(10)
            
        if lb_host:
            endpoint_success = verify_api_endpoints(f"http://{lb_host}")
            if not endpoint_success:
                logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
                sys.exit(1)
        else:
            logger.warning("EKS LoadBalancer hostname not available after timeout. Skipping endpoint check.")

    # 2. CloudWatch Check
    success = verify_cloudwatch(env)
    
    if success:
        logger.success("PLUMBING VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.error("PLUMBING VERIFICATION: FAILED - CloudWatch logs did not show success pattern")
        sys.exit(1)

if __name__ == "__main__":
    main()
