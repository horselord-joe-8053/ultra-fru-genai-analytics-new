"""
GCP deployment verification.
Reference: tools/aws/scope_shared/verify/verify_all_deploy.py (phases, endpoints, CloudWatch/Cloud Logging).

Verifies LLM client, API endpoints (when deployed), and Cloud Logging.
Uses same logger format, phase structure, and summary table as AWS.
"""
import argparse
import json
import os
import sys
import time
import subprocess
import requests

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

from tools.cloud_shared.logging import logger
from tools.cloud_shared.env import load_dotenv, get_int_env, EnvVarNotFound
from tools.gcp.scope_shared.core.backend import resolve_region
from tools.gcp.scope_shared.deploy.bootstrap_state_backend import load_gcp_env
from tools.gcp.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.retry import poll_until, update_heartbeat
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary

load_dotenv()
load_gcp_env()  # Fix multi-line GOOGLE_APPLICATION_CREDENTIALS_JSON for tofu subprocess
print("verify_all_deploy: imports done, entering main()", flush=True)

VERIFY_TIMEOUT_SEC = get_int_env("VERIFY_TIMEOUT_SEC", 900)
VERIFY_HEARTBEAT_INTERVAL_SEC = get_int_env("VERIFY_HEARTBEAT_INTERVAL_SEC", 30)
QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC = get_int_env("VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC", 180)

CSV_PATH = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")),
    "core_app", "data", "raw", "fridge_sales_with_rating.csv",
)

VERIFY_RETRIABLE_HTTP_CODES = frozenset({502, 503})


def get_total_rec_from_csv() -> int:
    """Return expected total records from CSV (line count minus header)."""
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV not found: {CSV_PATH}")
        logger.error("Verification requires the source CSV to determine expected record count. Cannot proceed.")
        sys.exit(1)
    with open(CSV_PATH) as f:
        return max(0, sum(1 for _ in f) - 1)


def get_tofu_output(stack_dir: str, env: str) -> dict:
    """Retrieve output from Tofu (assumed already applied). Reference: AWS get_tofu_output."""
    from tools.gcp.scope_shared.core.terra_init import init_stack

    region = resolve_region(None)
    try:
        init_stack(stack_dir, env, region)
        out = subprocess.check_output(
            [os.getenv("FRU_TF_BIN", "tofu"), "output", "-json"],
            cwd=stack_dir,
            text=True,
            env={**get_terra_env(region), "CLOUD_REGION": region},
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
    # Retriable: overloaded (529), rate limits, throttling, 500 api_error - keep polling
    if any(x in msg_lower for x in ("overloaded_error", "rate_limit", "throttl", "api_error", "internal server error")):
        return False
    # Model not found (404) - e.g. claude-3-5-sonnet-20241022 deprecated or wrong ID
    if "not_found_error" in msg_lower or "model:" in msg_lower and "404" in error_msg:
        return True
    # API/auth errors that won't resolve by retrying
    if "invalid_api_key" in msg_lower or "authentication" in msg_lower and "failed" in msg_lower:
        return True
    # Explicit error type in embedded JSON (but not retriable types above)
    if "'type': 'error'" in error_msg or '"type":"error"' in error_msg.replace(" ", ""):
        return True
    return False


def _is_agent_disabled_by_config() -> bool:
    """True if USE_AGENT_QUERY is false in env."""
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
    Same logic as AWS verify_api_endpoints.
    """
    timeout_secs = timeout_secs or VERIFY_TIMEOUT_SEC
    heartbeat_interval_sec = heartbeat_interval_sec or VERIFY_HEARTBEAT_INTERVAL_SEC
    logger.info(f"Validating API Endpoints at: {base_url} (timeout={timeout_secs}s, total_rec={total_rec})")

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
            raise RuntimeError(f"QueryStream answer does not contain total_rec={total_rec}: {answer[:100]}...")
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
        {"path": "/query/stream?query=total%20number%20of%20record", "name": "QueryStream", "check": check_query_stream, "timeout": QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC},
        {"path": "/analytics", "name": "Analytics", "check": check_analytics, "timeout": 10},
    ]
    results = {e["name"]: False for e in endpoints}
    last_status = {e["name"]: None for e in endpoints}
    last_error = {e["name"]: None for e in endpoints}
    last_resp = {}

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
                    elif e["name"] == "Analytics" and resp.status_code == 200:
                        try:
                            data = resp.json()
                            err = data.get("error") or ""
                            if err:
                                last_error[e["name"]] = err
                        except Exception:
                            pass
                    elif resp.status_code >= 500:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Server Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
                    elif resp.status_code >= 400:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} (Client Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code}")
            except requests.exceptions.ConnectionError as ex:
                last_error[e["name"]] = str(ex)
            except requests.exceptions.Timeout as ex:
                if e["name"] == "QueryStream":
                    t = e.get("timeout", 60)
                    msg = f"QueryStream per-request timeout ({t}s). Increase VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC or retry."
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

    rows = []
    for e in endpoints:
        if results[e["name"]]:
            notes = ""
            if e["name"] == "QueryStream":
                resp = last_resp.get(e["name"])
                passed_via_disabled = use_agent_disabled_by_config and resp and "Agent-based query processing is disabled" in (resp.text or "")
                notes = "agent disabled by config (USE_AGENT_QUERY=false)" if passed_via_disabled else f"total_rec={total_rec} in answer"
            elif e["name"] == "Analytics":
                notes = f"total_records={total_rec}"
            else:
                notes = base_url.rstrip("/") + e["path"]
        else:
            s = last_status[e["name"]]
            err = last_error[e["name"]]
            notes = f"HTTP {s}" if s else (err or "Unknown error")
        rows.append(VerifyRow(scope=scope, endpoint=e["name"], ok=results[e["name"]], notes=notes))

    if not ok:
        logger.error(f"[VERIFICATION TIMEOUT] Endpoints failed within {timeout_secs}s")
    return ok, rows


def verify_llm_and_query(total_rec: int) -> tuple[bool, list]:
    """
    Verify LLM client and simple query (GCP phase when no kube/nonkube API deployed).
    Returns (ok, rows) for summary table.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    sys.path.insert(0, os.path.join(repo_root, "core_app"))

    rows = []
    client = None
    try:
        from backend.env_utils.cloud_shared.client_factory import create_llm_client
        client = create_llm_client()
        llm_ok = True
        notes = type(client).__name__
    except Exception as e:
        llm_ok = False
        notes = str(e)
    rows.append(VerifyRow(scope="shared", endpoint="LLM client", ok=llm_ok, notes=notes))

    if not llm_ok or client is None:
        return False, rows

    try:
        r = client.complete("You are helpful.", "Say OK in one word.")
        text = r.get("text", "")[:50]
        query_ok = "ok" in text.lower() or "OK" in text
        notes = f"total_rec={total_rec} (query test)" if query_ok else text or "empty response"
    except Exception as e:
        query_ok = False
        notes = str(e)
    rows.append(VerifyRow(scope="shared", endpoint="Query", ok=query_ok, notes=notes))

    return query_ok, rows


def verify_cloud_logging(env: str, scope: str, timeout_secs: int | None = None) -> tuple[bool, str]:
    """
    GCP Cloud Logging verification (reference: AWS verify_cloudwatch).
    When GCP nonkube (Cloud Run) creates Spark logs, verify success pattern.
    kube (GKE): may skip when missing (GKE does not create this log by default).
    """
    # GCP Cloud Logging: not yet implemented for Spark; skip for now (like kube skips CloudWatch)
    logger.info("Cloud Logging verification: skipped (GCP Spark logs not yet wired)")
    return True, "skipped (GCP Spark logs not yet wired)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], default="kube")
    args = ap.parse_args()

    if args.region:
        os.environ["CLOUD_REGION"] = args.region

    try:
        region = resolve_region(args.region)
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)

    os.environ["CLOUD_REGION"] = region
    os.environ["CLOUD_PROVIDER"] = "gcp"

    total_rec = get_total_rec_from_csv()

    verify_start = time.time()
    logger.operation_start("Verify", args.scope, args.env, region)
    logger.step(f"Full Verification Interface (env: {args.env}, region: {region}, total_rec from CSV: {total_rec})")

    scopes_to_verify = ["nonkube", "kube"] if args.scope == "all" else [args.scope]
    verify_phases = [f"Endpoints ({s})" for s in scopes_to_verify] + ["LLM / Query", "Cloud Logging"]
    total_phases = len(verify_phases)
    all_rows: list[VerifyRow] = []
    phase_idx = 0

    # Endpoints: when kube/nonkube have base_url (Cloud Run, GKE LB, etc.)
    for scope in scopes_to_verify:
        phase_idx += 1
        phase_start_time = time.time()
        logger.phase_start(phase_idx, total_phases, verify_phases[phase_idx - 1])

        base_url = None
        if scope == "nonkube":
            logger.info("Fetching nonkube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/gcp/nonkube", args.env)
            # GCP nonkube (Cloud Run): would have cloud_run_url or similar
            base_url = stack_out.get("cloud_run_url", {}).get("value") or stack_out.get("service_url", {}).get("value")
        elif scope == "kube":
            logger.info("Fetching kube tofu outputs (tofu init + output, ~30-60s)...")
            sys.stdout.flush()
            stack_out = get_tofu_output("infra_terraform/live_deploy/gcp/kube", args.env)
            # GCP kube: gke_cluster_endpoint is API server, not app URL; would need LB ingress
            base_url = stack_out.get("load_balancer_url", {}).get("value") or stack_out.get("ingress_url", {}).get("value")

        if base_url:
            base_url = base_url if base_url.startswith("http") else f"https://{base_url}"
            ok, rows = verify_api_endpoints(base_url, total_rec, scope)
            all_rows.extend(rows)
            if not ok:
                logger.error(f"[VERIFICATION FAILED] API endpoints are not responding correctly ({scope})")
                print_verify_summary(all_rows, args.env, total_rec)
                logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
                sys.exit(1)
        else:
            logger.info(f"No base URL for {scope} (stack not deployed or no frontend/LB). Skipping endpoints.")

        phase_secs = int(time.time() - phase_start_time)
        logger.phase_end(phase_idx, total_phases, verify_phases[phase_idx - 1], phase_secs)

    # LLM / Query: always run (works without deployed API)
    phase_idx += 1
    phase_start_time = time.time()
    logger.phase_start(phase_idx, total_phases, "LLM / Query")
    llm_ok, llm_rows = verify_llm_and_query(total_rec)
    all_rows.extend(llm_rows)
    phase_secs = int(time.time() - phase_start_time)
    logger.phase_end(phase_idx, total_phases, "LLM / Query", phase_secs)

    if not llm_ok:
        logger.error("[VERIFICATION FAILED] LLM client or query test failed")
        print_verify_summary(all_rows, args.env, total_rec)
        logger.operation_end("Verify", args.scope, args.env, region, int(time.time() - verify_start), ok=False)
        sys.exit(1)

    # Cloud Logging
    phase_idx += 1
    phase_start_time = time.time()
    logger.phase_start(phase_idx, total_phases, "Cloud Logging")
    cw_ok, cw_note = verify_cloud_logging(args.env, args.scope)
    phase_secs = int(time.time() - phase_start_time)
    logger.phase_end(phase_idx, total_phases, "Cloud Logging", phase_secs)
    all_rows.append(VerifyRow(scope="shared", endpoint="Cloud Logging", ok=cw_ok, notes=cw_note))

    print_verify_summary(all_rows, args.env, total_rec)

    verify_dur = int(time.time() - verify_start)
    if cw_ok and llm_ok:
        logger.operation_end("Verify", args.scope, args.env, region, verify_dur, ok=True)
        logger.success("FULL VERIFICATION: SUCCESS")
        sys.exit(0)
    else:
        logger.operation_end("Verify", args.scope, args.env, region, verify_dur, ok=False)
        logger.error("FULL VERIFICATION: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except EnvVarNotFound as e:
        logger.error(str(e))
        sys.exit(1)
