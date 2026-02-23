import os
import sys
import time
import json
import subprocess
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, require, get_int_env, EnvVarNotFound
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.cloud_shared.retry import poll_until, update_heartbeat
from tools.aws.scope_shared.deploy.bootstrap_helpers import K8S_NAMESPACE
from tools.aws.scope_shared.core.terra_runner import ensure_shared_terra_env
from tools.aws.scope_shared.verify.verify_summary import VerifyRow, print_verify_summary

load_dotenv()
print("verify_all_deploy: imports done, entering main()", flush=True)

# Configurable via .env (aligned with legacy heartbeat/timeout pattern)
VERIFY_TIMEOUT_SEC = get_int_env("VERIFY_TIMEOUT_SEC", 900)  # CloudFront propagation can take 5-15 min
VERIFY_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)

# Per-request timeout for QueryStream: LLM streaming via Bedrock can take 60–120+ seconds.
# A short timeout (e.g. 60s) yields a generic "Read timed out" that obscures the real cause.
# We allow 3 min so the stream can complete; override via VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC.
QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC = get_int_env("VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC", 180)

# CSV path for total_rec (line count - 1)
CSV_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")), "core_app", "data", "raw", "fridge_sales_with_rating.csv")


def get_total_rec_from_csv() -> int:
    """Return expected total records from CSV (line count minus header)."""
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV not found: {CSV_PATH}")
        logger.error("Verification requires the source CSV to determine expected record count. Cannot proceed.")
        sys.exit(1)
    with open(CSV_PATH) as f:
        return max(0, sum(1 for _ in f) - 1)

# HTTP status codes treated as retriable during verification (transient "not-ready-yet" only).
# 403 Access Denied = real failure (OAC misconfig, empty S3, wrong bucket policy) - NOT retriable.
# 502/503 = may be transient (ECS/ALB not ready yet) - we poll until timeout; persistent 502/503 will fail.
VERIFY_RETRIABLE_HTTP_CODES = frozenset({502, 503})

def get_tofu_output(stack_dir, env):
    """Retrieve output from Tofu (assumed already applied)."""
    ensure_shared_terra_env()
    from tools.aws.scope_shared.deploy.deploy_common import init_stack
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(None)
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir, text=True, env={**os.environ, "CLOUD_REGION": region}
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


def verify_api_endpoints(
    base_url: str,
    total_rec: int,
    scope: str,
    timeout_secs=None,
    heartbeat_interval_sec=None,
) -> tuple[bool, list]:
    """
    Poll endpoints until all pass or timeout. Returns (ok, rows) for summary table.
    HTTP 502/503 and ConnectionError are retriable. 403 = real failure.
    """
    timeout_secs = timeout_secs or VERIFY_TIMEOUT_SEC
    heartbeat_interval_sec = heartbeat_interval_sec or VERIFY_HEARTBEAT_INTERVAL_SEC
    logger.info(f"Validating API Endpoints at: {base_url} (timeout={timeout_secs}s, total_rec={total_rec})")

    def check_query_stream(r):
        if r.status_code != 200:
            return False
        if "Agent-based query processing is disabled" in r.text:
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
        return True

    def check_analytics(r):
        if r.status_code != 200:
            return False
        try:
            data = r.json()
            err = data.get("error") or ""
            if err:
                if "database" in err.lower() and ("not configured" in err.lower() or "unreachable" in err.lower()):
                    return True
                raise RuntimeError(f"Analytics error (non-retriable): {err}")
            total_records = data.get("total_records") or 0
            if total_records != total_rec:
                return False
            return True
        except RuntimeError:
            raise
        except Exception:
            return r.status_code == 200

    endpoints = [
        {"path": "/health", "name": "Health", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/version", "name": "Version", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/", "name": "Frontend", "check": lambda r: r.status_code == 200 and "<html" in r.text.lower(), "timeout": 10},
        # QueryStream: per-request timeout 3 min (LLM streaming via Bedrock is slow)
        {"path": "/query/stream?query=total%20number%20of%20record", "name": "QueryStream", "check": check_query_stream, "timeout": QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC},
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
                    results[e["name"]] = True
                else:
                    if resp.status_code in VERIFY_RETRIABLE_HTTP_CODES:
                        last_error[e["name"]] = f"HTTP {resp.status_code}"
                    elif resp.status_code >= 500:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Server Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
                    elif resp.status_code >= 400:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Client Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
            except requests.exceptions.ConnectionError as ex:
                last_error[e["name"]] = str(ex)
            except requests.exceptions.Timeout as ex:
                # QueryStream: LLM streaming via Bedrock can exceed short timeouts; log clearly.
                if e["name"] == "QueryStream":
                    t = e.get("timeout", 60)
                    msg = (
                        f"QueryStream per-request timeout ({t}s). "
                        "LLM streaming via Bedrock often takes 60–120+ seconds. "
                        "Increase VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC or retry."
                    )
                    logger.warning(f"✗ {msg}")
                    last_error[e["name"]] = msg
                else:
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

    # Build rows for summary table
    rows = []
    for e in endpoints:
        url = base_url.rstrip("/") + e["path"]
        if results[e["name"]]:
            notes = url
            if e["name"] == "QueryStream":
                notes = f"total_rec={total_rec} in answer"
            elif e["name"] == "Analytics":
                notes = f"total_records={total_rec}"
        else:
            s = last_status[e["name"]]
            err = last_error[e["name"]]
            notes = f"HTTP {s}" if s else (err or "Unknown error")
        rows.append(VerifyRow(scope=scope, endpoint=e["name"], ok=results[e["name"]], notes=notes))

    if not ok:
        logger.error(f"[VERIFICATION TIMEOUT] Endpoints failed within {timeout_secs}s")
    return ok, rows

def verify_cloudwatch(env, timeout_mins=None) -> tuple[bool, str]:
    """Return (ok, note) for summary table."""
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(None)
    log_group = os.getenv("CLOUDWATCH_LOG_GROUP") or f"/fru/{env}/spark"

    timeout_secs = (timeout_mins * 60) if timeout_mins else get_int_env("LOGGING_TASK_DEFAULT_TIMEOUT", VERIFY_TIMEOUT_SEC)
    heartbeat_interval = VERIFY_HEARTBEAT_INTERVAL_SEC

    logger.info(f"Monitoring CloudWatch Log Group: {log_group} (timeout={timeout_secs}s)")
    
    start_time = time.time()
    
    try:
        out = subprocess.check_output([
            "aws", "logs", "describe-log-groups",
            "--log-group-name-prefix", log_group,
            "--region", region
        ], text=True)
        groups = json.loads(out).get("logGroups", [])
        if not any(g["logGroupName"] == log_group for g in groups):
            logger.warning(f"Log group {log_group} not found. Skipping log verification.")
            return True, "log group not found (skipped)"
    except Exception as e:
        logger.warning(f"Log group check failed. Skipping log verification. ({e})")
        return True, "check failed (skipped)"

    last_heartbeat = 0
    while (time.time() - start_time) < timeout_secs:
        elapsed = int(time.time() - start_time)
        last_heartbeat = update_heartbeat(
            elapsed, last_heartbeat, heartbeat_interval,
            f"  Still waiting for CloudWatch logs... {elapsed} s elapsed",
        )

        try:
            streams = subprocess.check_output([
                "aws", "logs", "describe-log-streams",
                "--log-group-name", log_group,
                "--order-by", "LastEventTime",
                "--descending",
                "--limit", "3",
                "--region", region
            ], text=True)
            
            stream_list = json.loads(streams).get("logStreams", [])
            
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
                    return True, f"{log_group} — success pattern in {stream_name}"
                elif "fru bootstrap start" in log_content:
                    pass  # still waiting
                
        except Exception as e:
            logger.warning(f"Waiting for logs... ({e})")

        time.sleep(min(15, heartbeat_interval))

    logger.error(f"Timed out waiting for success logs after {timeout_secs}s.")
    return False, f"timeout after {timeout_secs}s"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    args = ap.parse_args()
    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    logger.info("Verify script started (fetching tofu outputs next, may take 30-60s)...")
    sys.stdout.flush()
    
    env = args.env
    get_base_vars(env) # ensure env vars are set for subprocesses
    
    total_rec = get_total_rec_from_csv()
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)
    logger.step(f"Full Verification Interface (env: {env}, region: {region}, total_rec from CSV: {total_rec})")
    
    # When scope=all, verify nonkube first then kube (matches deploy order)
    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    all_rows: list[VerifyRow] = []
    
    # 1. Endpoint Check
    for scope in scopes_to_verify:
        if scope == "nonkube":
            logger.info("Fetching nonkube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/aws/nonkube", env)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            alb_dns = stack_out.get("alb_dns_name", {}).get("value")
            base_url = f"https://{cf_domain}" if cf_domain else (f"http://{alb_dns}" if alb_dns else None)
            if base_url:
                ok, rows = verify_api_endpoints(base_url, total_rec, scope="nonkube")
                all_rows.extend(rows)
                if not ok:
                    logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (nonkube)")
                    print_verify_summary(all_rows, env, total_rec)
                    sys.exit(1)
            else:
                logger.error("Could not find CloudFront domain or ALB DNS in terraform outputs (nonkube).")
                sys.exit(1)
        elif scope == "kube":
            logger.info("Fetching kube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/aws/kube", env)
            cf_domain = stack_out.get("cloudfront_domain_name", {}).get("value")
            if cf_domain:
                base_url = f"https://{cf_domain}"
                ok, rows = verify_api_endpoints(base_url, total_rec, scope="kube")
                all_rows.extend(rows)
                if not ok:
                    logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (kube)")
                    print_verify_summary(all_rows, env, total_rec)
                    sys.exit(1)
            else:
                # Fallback: wait for K8s LoadBalancer hostname
                logger.info("Waiting for EKS LoadBalancer hostname...")
                lb_host = ""
                for _ in range(30):
                    try:
                        cmd = ["kubectl", "get", "svc", "fru-api-svc", "-n", K8S_NAMESPACE, "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"]
                        lb_host = subprocess.check_output(cmd, text=True).strip()
                        if lb_host:
                            break
                    except Exception:
                        pass
                    time.sleep(10)

                if lb_host:
                    ok, rows = verify_api_endpoints(f"http://{lb_host}", total_rec, scope="kube")
                    all_rows.extend(rows)
                    if not ok:
                        logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly (kube)")
                        print_verify_summary(all_rows, env, total_rec)
                        sys.exit(1)
                else:
                    logger.warning("EKS LoadBalancer hostname not available after timeout. Skipping endpoint check (kube).")

    # 2. CloudWatch Check
    cw_ok, cw_note = verify_cloudwatch(env)
    all_rows.append(VerifyRow(scope="shared", endpoint="CloudWatch", ok=cw_ok, notes=cw_note))
    
    # 3. Print summary table (no logger prefix)
    print_verify_summary(all_rows, env, total_rec)
    
    if cw_ok:
        logger.success("FULL VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.error("FULL VERIFICATION: FAILED - CloudWatch logs did not show success pattern")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
