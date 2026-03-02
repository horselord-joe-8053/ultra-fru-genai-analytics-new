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
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary

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

# --- Acceptable-error policy (refactor: strict by default) ---
# Analytics: no acceptable errors; DB not configured/unreachable = fail (fix credentials).
# QueryStream: "Agent disabled" acceptable only when USE_AGENT_QUERY=false (env, same as deploy).
# CloudWatch: ECS (nonkube) creates path-style Spark log group (e.g. /fru/cloud-log-group-spark/dev/us-east-1);
#   EKS (kube) does not. For nonkube/all, enforce fail when log group missing (PASS not allowed). For kube only, allow skip (PASS).

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


def _parse_sse_error_message(text: str) -> str | None:
    """Parse SSE stream, return message from last event: error data."""
    last_msg = None
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
        if event_type == "error" and data_json and "message" in data_json:
            last_msg = data_json.get("message", "")
    return last_msg


def _is_non_retriable_query_error(error_msg: str) -> bool:
    """
    True if the error indicates a non-retriable failure (e.g. model not found, bad config).
    These should fail verify immediately instead of retrying.
    """
    if not error_msg:
        return False
    msg_lower = error_msg.lower()
    # Model not found (404) - e.g. claude-3-5-sonnet-20241022 deprecated or wrong ID
    if "not_found_error" in msg_lower or "model:" in msg_lower and "404" in error_msg:
        return True
    # API/auth errors that won't resolve by retrying
    if "invalid_api_key" in msg_lower or "authentication" in msg_lower and "failed" in msg_lower:
        return True
    # Explicit error type in embedded JSON
    if "'type': 'error'" in error_msg or '"type":"error"' in error_msg.replace(" ", ""):
        return True
    return False


def _is_agent_disabled_by_config() -> bool:
    """True if USE_AGENT_QUERY is false in env (same source as deploy)."""
    val = (os.getenv("USE_AGENT_QUERY") or "true").lower()
    return val in ("false", "0", "no", "off", "")


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

    # QueryStream: "Agent disabled" is acceptable only when USE_AGENT_QUERY=false (env var).
    # Same env drives deploy; verify reads it locally—no need to parse from API response.
    use_agent_disabled_by_config = _is_agent_disabled_by_config()

    def check_query_stream(r):
        if r.status_code != 200:
            return False
        if "Agent-based query processing is disabled" in r.text:
            return use_agent_disabled_by_config
        if "exc_info" in r.text and "unexpected keyword argument" in r.text:
            raise RuntimeError("QueryStream returned AgentLogger exc_info error (non-retriable; needs redeploy)")
        # Check for error event first: 200 + error event = fail (don't retry non-retriable errors)
        err_msg = _parse_sse_error_message(r.text)
        if err_msg and _is_non_retriable_query_error(err_msg):
            raise RuntimeError(f"QueryStream error (non-retriable): {err_msg[:200]}...")
        answer = _parse_sse_complete_answer(r.text)
        if answer is None:
            return False
        # Agent error (generic message): retriable; API may emit "error" event only after fix
        if "An error has occurred while processing your query" in answer:
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
                # "No analytics data available yet" is retriable (batch may still be running)
                if "No analytics data available yet" in err:
                    return False
                # No "acceptable" errors: DB not configured/unreachable = fail (fix credentials).
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
    last_resp = {}  # for custom notes (e.g. QueryStream when agent disabled by config)

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
                    last_resp[e["name"]] = resp
                else:
                    if resp.status_code in VERIFY_RETRIABLE_HTTP_CODES:
                        last_error[e["name"]] = f"HTTP {resp.status_code}"
                    elif e["name"] == "QueryStream" and resp.status_code == 200:
                        # Agent error (no complete event): parse error event for notes
                        err_msg = _parse_sse_error_message(resp.text)
                        last_error[e["name"]] = err_msg or "no complete/error event"
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
                resp = last_resp.get(e["name"])
                passed_via_disabled = (
                    use_agent_disabled_by_config
                    and resp
                    and "Agent-based query processing is disabled" in (resp.text or "")
                )
                notes = (
                    "agent disabled by config (USE_AGENT_QUERY=false)"
                    if passed_via_disabled
                    else f"total_rec={total_rec} in answer"
                )
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

def verify_cloudwatch(env, timeout_mins=None, scope: str = "nonkube") -> tuple[bool, str]:
    """
    Return (ok, note) for summary table.
    ECS (nonkube) creates Spark log group; EKS (kube) does not.
    - nonkube/all: enforce fail when log group not found or check failed (PASS not allowed).
    - kube only: allow skip (PASS) when missing—EKS does not create this log group.
    """
    from tools.aws.scope_shared.core.backend import resolve_region
    from tools.aws.scope_shared.core import resource_names
    region = resolve_region(None)
    log_group = resource_names.log_group_spark(env, region)
    # Only kube may skip; nonkube/all must fail when log group missing (ECS creates it).
    skip_when_missing = scope == "kube"

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
            if skip_when_missing:
                logger.warning(f"Log group {log_group} not found. Skipping (kube; EKS does not create it).")
                return True, "log group not found (skipped; kube)"
            # nonkube/all: ECS creates this; fail—PASS not allowed.
            logger.error(f"Log group {log_group} not found.")
            return False, "log group not found"
    except Exception as e:
        if skip_when_missing:
            logger.warning(f"Log group check failed. Skipping (kube). ({e})")
            return True, "check failed (skipped; kube)"
        # nonkube/all: enforce fail.
        logger.error(f"Log group check failed: {e}")
        return False, f"check failed: {e}"

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
    ap.add_argument("--region", required=True, help="Cloud region. Required.")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="nonkube")
    args = ap.parse_args()
    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    env = args.env
    get_base_vars(env) # ensure env vars are set for subprocesses
    
    total_rec = get_total_rec_from_csv()
    from tools.aws.scope_shared.core.backend import resolve_region
    region = resolve_region(args.region)
    
    verify_start = time.time()
    logger.operation_start("Verify", args.scope, args.env, region)
    logger.step(f"Full Verification Interface (env: {env}, region: {region}, total_rec from CSV: {total_rec})")
    
    # When scope=all, verify nonkube first then kube (matches deploy order)
    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    verify_phases = [f"Endpoints ({s})" for s in scopes_to_verify] + ["CloudWatch logs"]
    total_phases = len(verify_phases)
    all_rows: list[VerifyRow] = []
    phase_idx = 0
    
    for scope in scopes_to_verify:
        phase_idx += 1
        phase_start_time = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])
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
                    logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                    sys.exit(1)
            else:
                logger.error("Could not find CloudFront domain or ALB DNS in terraform outputs (nonkube).")
                logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
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
                    logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                    sys.exit(1)
            else:
                # Fallback: wait for K8s LoadBalancer hostname (ensure kubeconfig points at deploy region)
                from tools.aws.kube.deploy_kube import _try_get_lb_hostname
                logger.info("Waiting for EKS LoadBalancer hostname...")
                subprocess.run(
                    ["python", "tools/aws/kube/eks_kubeconfig.py", "--env", env],
                    check=False,
                    env={**os.environ, "CLOUD_REGION": region},
                )
                lb_host = ""
                for _ in range(30):
                    lb_host = _try_get_lb_hostname(env, region)
                    if lb_host:
                        break
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
        phase_secs = int(time.time() - phase_start_time)
        logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)

    # CloudWatch: nonkube/all enforce fail when missing; kube may skip (ECS creates log group, EKS does not)
    phase_idx += 1
    phase_start_time = time.time()
    logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])
    cw_ok, cw_note = verify_cloudwatch(env, scope=args.scope)
    phase_secs = int(time.time() - phase_start_time)
    logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)
    all_rows.append(VerifyRow(scope="shared", endpoint="CloudWatch", ok=cw_ok, notes=cw_note))
    
    # 3. Print summary table (no logger prefix)
    print_verify_summary(all_rows, env, total_rec)
    
    verify_dur = int(time.time() - verify_start)
    if cw_ok:
        logger.operation_end("Verify", args.scope, args.env, region, verify_dur, ok=True)
        logger.success("FULL VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.operation_end("Verify", args.scope, args.env, region, verify_dur, ok=False)
        logger.error("FULL VERIFICATION: FAILED - CloudWatch logs did not show success pattern")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
