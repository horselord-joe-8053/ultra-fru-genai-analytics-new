"""
Shared API endpoint verification: poll Health, Version, Frontend, QueryStream, Analytics.

Used by AWS and GCP verify_all_deploy. Provider param is for VerifyRow only (aws|gcp).
HTTP 502/503 and ConnectionError are retriable; 403 = real failure.
"""
import requests

from tools.cloud_shared.logging import logger
from tools.cloud_shared.retry import poll_until
from tools.cloud_shared.verify.verify_config import (
    VERIFY_RETRIABLE_HTTP_CODES,
    VERIFY_TIMEOUT_SEC,
    VERIFY_HEARTBEAT_INTERVAL_SEC,
    QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC,
)
from tools.cloud_shared.verify.verify_sse import (
    parse_sse_complete_answer,
    parse_sse_error_message,
    is_non_retriable_query_error,
    is_agent_disabled_by_config,
)
from tools.cloud_shared.verify.verify_summary import VerifyRow


def verify_api_endpoints(
    base_url: str,
    total_rec: int,
    scope: str,
    provider: str,
    timeout_secs: int | None = None,
    heartbeat_interval_sec: int | None = None,
    query_stream_timeout_sec: int | None = None,
    skip_frontend: bool = False,
) -> tuple[bool, list[VerifyRow]]:
    """
    Poll endpoints until all pass or timeout. Returns (ok, rows) for summary table.
    provider: aws or gcp (for VerifyRow). Timeouts default to verify_config values.
    """
    timeout_secs = timeout_secs or VERIFY_TIMEOUT_SEC
    heartbeat_interval_sec = heartbeat_interval_sec or VERIFY_HEARTBEAT_INTERVAL_SEC
    query_stream_timeout_sec = query_stream_timeout_sec or QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC

    logger.info(f"Validating API Endpoints at: {base_url} (timeout={timeout_secs}s, total_rec={total_rec})")
    use_agent_disabled_by_config = is_agent_disabled_by_config()

    def check_query_stream(r):
        if r.status_code != 200:
            return False
        if "Agent-based query processing is disabled" in r.text:
            return use_agent_disabled_by_config
        if "exc_info" in r.text and "unexpected keyword argument" in r.text:
            raise RuntimeError("QueryStream returned AgentLogger exc_info error (non-retriable; needs redeploy)")
        err_msg = parse_sse_error_message(r.text)
        if err_msg and is_non_retriable_query_error(err_msg):
            raise RuntimeError(f"QueryStream error (non-retriable): {err_msg[:200]}...")
        answer = parse_sse_complete_answer(r.text)
        if answer is None:
            return False
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
                if "No analytics data available yet" in err:
                    return False
                raise RuntimeError(f"Analytics error (non-retriable): {err}")
            total_records = data.get("total_records") or 0
            return total_records == total_rec
        except RuntimeError:
            raise
        except Exception:
            return r.status_code == 200

    endpoints = [
        {"path": "/health", "name": "Health", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/version", "name": "Version", "check": lambda r: r.status_code == 200, "timeout": 10},
        {"path": "/", "name": "Frontend", "check": lambda r: r.status_code == 200 and "<html" in r.text.lower(), "timeout": 10},
        {"path": "/query/stream?query=total%20number%20of%20record", "name": "QueryStream", "check": check_query_stream, "timeout": query_stream_timeout_sec},
        {"path": "/analytics", "name": "Analytics", "check": check_analytics, "timeout": 10},
    ]
    if skip_frontend:
        endpoints = [e for e in endpoints if e["name"] != "Frontend"]
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
                        err_msg = parse_sse_error_message(resp.text)
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
                try:
                    data = last_resp.get(e["name"])
                    total_records = data.json().get("total_records", 0) if data else 0
                    notes = f"total_records={total_records}"
                except Exception:
                    notes = "has data"
        else:
            s = last_status[e["name"]]
            err = last_error[e["name"]]
            notes = f"HTTP {s}" if s else (err or "Unknown error")
        rows.append(VerifyRow(provider=provider, scope=scope, endpoint=e["name"], ok=results[e["name"]], notes=notes))

    if not ok:
        logger.error(f"[VERIFICATION TIMEOUT] Endpoints failed within {timeout_secs}s")
    return ok, rows
