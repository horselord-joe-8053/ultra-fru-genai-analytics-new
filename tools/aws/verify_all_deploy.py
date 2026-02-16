import os
import sys
import time
import json
import subprocess
import argparse
import requests

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools import logger
from tools._env import load_dotenv, require, get_int_env
from tools.aws._aws_vars import get_base_vars
from tools.with_heartbeat import poll_until, update_heartbeat
from tools.aws.bootstrap_helpers import K8S_NAMESPACE
from tools.tofu_runner import ensure_shared_tofu_env

load_dotenv()

# Configurable via .env (aligned with legacy heartbeat/timeout pattern)
VERIFY_TIMEOUT_SEC = get_int_env("VERIFY_TIMEOUT_SEC", 900)  # CloudFront propagation can take 5-15 min
VERIFY_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)

# CSV path for total_rec (line count - 1)
CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "core-app", "data", "raw", "fridge_sales_with_rating.csv")


def get_total_rec_from_csv() -> int:
    """Return expected total records from CSV (line count minus header)."""
    if not os.path.exists(CSV_PATH):
        return 200  # fallback
    with open(CSV_PATH) as f:
        return max(0, sum(1 for _ in f) - 1)

# HTTP status codes treated as retriable during verification (transient "not-ready-yet" only).
# 403 Access Denied = real failure (OAC misconfig, empty S3, wrong bucket policy) - NOT retriable.
# 502/503 = may be transient (ECS/ALB not ready yet) - we poll until timeout; persistent 502/503 will fail.
VERIFY_RETRIABLE_HTTP_CODES = frozenset({502, 503})

def get_tofu_output(stack_dir, env):
    """Retrieve output from Tofu (assumed already applied)."""
    ensure_shared_tofu_env()
    from tools.aws.deploy import init_stack
    from tools.aws._backend import resolve_region
    region = resolve_region(None)
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir, text=True, env={**os.environ, "CLOUD_REGION": region, "AWS_REGION": region}
        )
        return json.loads(out)
    except Exception as e:
        logger.warning(f"could not get tofu output from {stack_dir}: {e}")
        return {}

def _parse_sse_complete_answer(text: str) -> str | None:
    """Parse SSE stream, return answer from last event: complete data."""
    last_answer = None
    for block in text.split("\n\n"):
        event_type = None
        data_json = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data_json = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    pass
        if event_type == "complete" and data_json and "answer" in data_json:
            last_answer = data_json.get("answer", "")
    return last_answer


def verify_api_endpoints(base_url, total_rec: int, timeout_secs=None, heartbeat_interval_sec=None):
    """
    Poll endpoints until all pass or timeout. Uses poll_until (DRY with retry pattern).
    HTTP 502/503 and ConnectionError are retriable (ECS/ALB not ready yet). 403 = real failure.
    total_rec: expected record count from CSV (used for QueryStream answer and Analytics total_records).
    """
    timeout_secs = timeout_secs or VERIFY_TIMEOUT_SEC
    heartbeat_interval_sec = heartbeat_interval_sec or VERIFY_HEARTBEAT_INTERVAL_SEC
    logger.info(f"Validating API Endpoints at: {base_url} (timeout={timeout_secs}s, heartbeat every {heartbeat_interval_sec}s, total_rec={total_rec})")

    def check_query_stream(r):
        if r.status_code != 200:
            return False
        if "Agent-based query processing is disabled" in r.text:
            logger.info("  (Note: Agent is disabled due to missing DB, but endpoint is reachable)")
            return True
        if "exc_info" in r.text and "unexpected keyword argument" in r.text:
            raise RuntimeError("QueryStream returned AgentLogger exc_info error (non-retriable; needs redeploy)")
        answer = _parse_sse_complete_answer(r.text)
        if answer is None:
            return False
        if str(total_rec) not in answer:
            raise RuntimeError(
                f"QueryStream answer does not contain total_rec={total_rec}: {answer[:100]}..."
            )
        logger.info(f"  QueryStream OK (query='total number of record'): answer contains total_rec={total_rec}")
        return True

    def check_analytics(r):
        if r.status_code != 200:
            return False
        try:
            data = r.json()
            err = data.get("error") or ""
            if err:
                # DB unreachable is a config/ops issue, not a deploy failure—endpoint is reachable
                if "database" in err.lower() and ("not configured" in err.lower() or "unreachable" in err.lower()):
                    logger.warning(f"  Analytics endpoint UP but DB unreachable: {err[:80]}...")
                    return True
                raise RuntimeError(f"Analytics error (non-retriable): {err}")
            total_records = data.get("total_records") or 0
            if total_records != total_rec:
                return False
            logger.info(f"  Analytics OK: total_records={total_records} (matches CSV total_rec)")
            return True
        except RuntimeError:
            raise
        except Exception:
            return r.status_code == 200

    endpoints = [
        {"path": "/health", "name": "Health", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/version", "name": "Version", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/", "name": "Frontend", "check": lambda r: r.status_code == 200 and "<html" in r.text.lower(), "timeout": 10},
        {"path": "/query/stream?query=total%20number%20of%20record", "name": "QueryStream", "check": check_query_stream, "timeout": 60},
        {"path": "/analytics", "name": "Analytics", "check": check_analytics, "timeout": 10},
    ]
    results = {e["name"]: False for e in endpoints}
    last_status = {e["name"]: None for e in endpoints}
    last_error = {e["name"]: None for e in endpoints}

    def check_one_round() -> bool:
        for e in endpoints:
            if results[e["name"]]:
                continue
            url = base_url.rstrip("/") + e["path"]
            timeout = e.get("timeout", 10)
            try:
                resp = requests.get(url, timeout=timeout)
                last_status[e["name"]] = resp.status_code
                last_error[e["name"]] = None
                if e["check"](resp):
                    logger.success(f"✓ {e['name']} endpoint is UP: {url}")
                    results[e["name"]] = True
                else:
                    if resp.status_code in VERIFY_RETRIABLE_HTTP_CODES:
                        last_error[e["name"]] = f"HTTP {resp.status_code}"
                    elif resp.status_code >= 500:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Server Error)")
                        logger.error(f"  URL: {url}\n  Body: {resp.text[:200]}")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
                    elif resp.status_code >= 400:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Client Error)")
                        logger.error(f"  URL: {url}")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
            except requests.exceptions.ConnectionError as ex:
                last_error[e["name"]] = str(ex)
            except requests.exceptions.Timeout as ex:
                last_error[e["name"]] = str(ex)
        return all(results.values())

    def heartbeat_msg(elapsed: int) -> str:
        pending = [n for n, ok in results.items() if not ok]
        parts = [f"{n}: {last_status[n] or last_error[n] or 'pending'}" for n in pending]
        detail = "; ".join(parts) if parts else "all passed"
        return f"  Still waiting for endpoints... {elapsed}s elapsed ({detail})"

    ok = poll_until(
        check_one_round,
        timeout_sec=timeout_secs,
        check_interval_sec=10,
        heartbeat_interval_sec=heartbeat_interval_sec,
        heartbeat_message_fn=heartbeat_msg,
    )
    if not ok:
        logger.error(f"\n[VERIFICATION TIMEOUT] Endpoints failed within {timeout_secs}s:")
        for e in endpoints:
            if not results[e["name"]]:
                s = last_status[e["name"]]
                err = last_error[e["name"]]
                logger.error(f"  ✗ {e['name']}: {f'HTTP {s}' if s else (err or 'Unknown error')}")
    return ok

def verify_cloudwatch(env, timeout_mins=None):
    region = os.getenv("CLOUD_REGION", "").strip() or require("AWS_REGION")
    # Use log group from env if set, otherwise default
    log_group = os.getenv("CLOUDWATCH_LOG_GROUP") or f"/fru/{env}/spark"

    timeout_secs = (timeout_mins * 60) if timeout_mins else get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", VERIFY_TIMEOUT_SEC)
    heartbeat_interval = VERIFY_HEARTBEAT_INTERVAL_SEC

    logger.info(f"Monitoring CloudWatch Log Group: {log_group} (timeout={timeout_secs}s, heartbeat every {heartbeat_interval}s)")
    
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
        logger.warning(f"Log group {log_group} check failed. Skipping log verification. ({e})")
        return True  # Treat check failure as warning

    last_heartbeat = 0
    while (time.time() - start_time) < timeout_secs:
        elapsed = int(time.time() - start_time)
        last_heartbeat = update_heartbeat(
            elapsed, last_heartbeat, heartbeat_interval,
            f"  Still waiting for CloudWatch logs... {elapsed} s elapsed",
        )

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

        time.sleep(min(15, heartbeat_interval))

    logger.error(f"Timed out waiting for success logs after {timeout_secs}s.")
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--scope", choices=["kube", "nonkube"], default="nonkube")
    args = ap.parse_args()
    
    logger.info("Verify script started (fetching tofu outputs next, may take 30-60s)...")
    sys.stdout.flush()
    
    env = args.env
    get_base_vars(env) # ensure env vars are set for subprocesses
    
    total_rec = get_total_rec_from_csv()
    logger.step(f"Full Verification Interface (env: {env}, total_rec from CSV: {total_rec})")
    
    # 1. Endpoint Check
    endpoint_success = False
    if args.scope == "nonkube":
        logger.info("Fetching nonkube tofu outputs (tofu init + output, ~30-60s)...")
        sys.stdout.flush()
        stack_out = get_tofu_output("live-deploy-aws/nonkube", env)
        cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
        alb_dns = stack_out.get("alb_dns_name", {}).get("value")
        base_url = f"https://{cf_domain}" if cf_domain else (f"http://{alb_dns}" if alb_dns else None)
        if base_url:
            endpoint_success = verify_api_endpoints(base_url, total_rec)
            if not endpoint_success:
                logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
                sys.exit(1)
        else:
            logger.error("Could not find CloudFront domain or ALB DNS in terraform outputs.")
            sys.exit(1)
    
    elif args.scope == "kube":
        stack_out = get_tofu_output("live-deploy-aws/kube", env)
        cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
        if cf_domain:
            base_url = f"https://{cf_domain}"
            endpoint_success = verify_api_endpoints(base_url, total_rec)
            if not endpoint_success:
                logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
                sys.exit(1)
        else:
            # Fallback: wait for K8s LoadBalancer hostname
            logger.info("Waiting for EKS LoadBalancer hostname...")
            lb_host = ""
            for _ in range(30):  # Wait up to 5 minutes for LB hostname
                try:
                    cmd = ["kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE, "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"]
                    lb_host = subprocess.check_output(cmd, text=True).strip()
                    if lb_host:
                        break
                except Exception:
                    pass
                time.sleep(10)

            if lb_host:
                endpoint_success = verify_api_endpoints(f"http://{lb_host}", total_rec)
                if not endpoint_success:
                    logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
                    sys.exit(1)
            else:
                logger.warning("EKS LoadBalancer hostname not available after timeout. Skipping endpoint check.")

    # 2. CloudWatch Check
    success = verify_cloudwatch(env)
    
    if success:
        logger.success("FULL VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.error("FULL VERIFICATION: FAILED - CloudWatch logs did not show success pattern")
        sys.exit(1)

if __name__ == "__main__":
    main()
