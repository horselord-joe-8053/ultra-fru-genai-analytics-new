"""
Shared API endpoint verification: poll Health, Version, Frontend, QueryStream, Analytics.

Used by AWS and GCP verify_all_deploy. Provider param is for VerifyRow only (aws|gcp).
HTTP 502/503 and ConnectionError are retriable; 403 = real failure.
"""
import os
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


def _fetch_agent_init_error(base_url: str) -> str | None:
    """GET /version and return agent_init_error from JSON so verify can log the real reason."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/version", timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        return (data.get("agent_init_error") or "").strip() or None
    except Exception:
        return None


def _debug_query_stream_response(resp: requests.Response, total_rec: int) -> None:
    """When DEBUG_VERIFY_QUERY_STREAM=1, write raw response to file for diagnosis."""
    try:
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "fru_verify_querystream_debug.txt")
        with open(path, "w") as f:
            f.write(f"status={resp.status_code} total_rec={total_rec}\n")
            f.write("---\n")
            f.write(resp.text or "(empty)")
        logger.warning(f"DEBUG_VERIFY_QUERY_STREAM: wrote raw response to {path} (len={len(resp.text or '')})")
        # Log snippet: first/last 400 chars
        text = resp.text or ""
        if len(text) > 800:
            snippet = f"{text[:400]}...\n...{text[-400:]}"
        else:
            snippet = text
        logger.warning(f"QueryStream response snippet:\n{snippet}")
    except Exception as ex:
        logger.warning(f"DEBUG_VERIFY_QUERY_STREAM write failed: {ex}")


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

    def check_query_stream(r, url: str = ""):
        if r.status_code != 200:
            return False

        # Special-case the "agent disabled" SSE error. The backend currently uses a single
        # phrase for both "disabled by config" and "failed to initialize", so we unwrap
        # those here into:
        #   - feature disabled by configuration (treat as OK), vs
        #   - agent init failure (treat as non-retriable backend error).
        if "Agent-based query processing is disabled" in (r.text or ""):
            err_msg = parse_sse_error_message(r.text) or "Agent-based query processing is disabled"
            real_reason = _fetch_agent_init_error(base_url)

            if use_agent_disabled_by_config and not real_reason:
                # Agent is intentionally off (USE_AGENT_QUERY=false) – deployment is healthy,
                # just without agent-based query enabled.
                return True

            # Otherwise this is an internal agent bootstrap/init error. Prefer the structured
            # reason from /version.agent_init_error so verify and logs point at the real cause.
            if real_reason:
                logger.error(f"Agent query init error from API: {real_reason}")
                err_msg = real_reason
            raise RuntimeError(f"QueryStream agent init failed (non-retriable): {err_msg} at {url}")
        if "exc_info" in r.text and "unexpected keyword argument" in r.text:
            raise RuntimeError(f"QueryStream returned AgentLogger exc_info error (non-retriable; needs redeploy) at {url}")
        err_msg = parse_sse_error_message(r.text)
        if err_msg and is_non_retriable_query_error(err_msg):
            raise RuntimeError(f"QueryStream error (non-retriable): {err_msg[:200]}... at {url}")
        answer = parse_sse_complete_answer(r.text)
        if answer is None:
            return False
        if "An error has occurred while processing your query" in answer:
            return False
        if str(total_rec) not in answer:
            raise RuntimeError(f"QueryStream answer does not contain total_rec={total_rec}: {answer[:100]}... at {url}")
        return True

    def check_analytics(r, url: str = ""):
        if r.status_code != 200:
            return False
        try:
            data = r.json()
            err = data.get("error") or ""
            if err:
                if "No analytics data available yet" in err:
                    return False
                raise RuntimeError(f"Analytics error (non-retriable): {err} at {url}")
            total_records = data.get("total_records") or 0
            return total_records == total_rec
        except RuntimeError:
            raise
        except Exception:
            return r.status_code == 200

    endpoints = [
        {"path": "/health", "name": "Health", "check": lambda r, url=None: r.status_code == 200, "timeout": 10},
        {"path": "/version", "name": "Version", "check": lambda r, url=None: r.status_code == 200, "timeout": 10},
        {"path": "/", "name": "Frontend", "check": lambda r, url=None: r.status_code == 200 and "<html" in r.text.lower(), "timeout": 10},
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
                if e["check"](resp, url):
                    results[e["name"]] = True
                    last_resp[e["name"]] = resp
                else:
                    if resp.status_code in VERIFY_RETRIABLE_HTTP_CODES:
                        last_error[e["name"]] = f"HTTP {resp.status_code}"
                    elif e["name"] == "QueryStream" and resp.status_code == 200:
                        err_msg = parse_sse_error_message(resp.text)
                        last_error[e["name"]] = err_msg or "no complete/error event"
                        # Debug: capture raw response when 200 but check failed (parse_sse_complete_answer returned None)
                        if os.environ.get("DEBUG_VERIFY_QUERY_STREAM"):
                            _debug_query_stream_response(resp, total_rec)
                    elif e["name"] == "Analytics" and resp.status_code == 200:
                        try:
                            data = resp.json()
                            err = data.get("error") or ""
                            if err:
                                last_error[e["name"]] = err
                        except Exception:
                            pass
                    elif resp.status_code >= 500:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} at {url} (Server Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code} at {url}")
                    elif resp.status_code >= 400:
                        logger.error(f"✗ {e['name']} returned {resp.status_code} at {url} (Client Error)")
                        raise RuntimeError(f"Non-retriable: {e['name']} HTTP {resp.status_code} at {url}")
            except requests.exceptions.ConnectionError as ex:
                last_error[e["name"]] = f"{url} → {ex}"
            except requests.exceptions.Timeout as ex:
                if e["name"] == "QueryStream":
                    t = e.get("timeout", 60)
                    msg = f"QueryStream per-request timeout ({t}s) at {url}. Increase VERIFY_QUERY_STREAM_TIMEOUT_PER_REQUEST_SEC or retry."
                    logger.warning(f"✗ {msg}")
                    last_error[e["name"]] = msg
                else:
                    last_error[e["name"]] = f"{url} → {ex}"
        return all(results.values())

    def heartbeat_msg(elapsed: int) -> str:
        pending = [n for n, ok in results.items() if not ok]
        base = base_url.rstrip("/")
        # Prefer last_error over last_status; include full URL (with port) for each pending endpoint
        parts = []
        for n in pending:
            path = next((e["path"] for e in endpoints if e["name"] == n), "")
            full_url = base + path if path else base
            status = last_error[n] or last_status[n] or "pending"
            parts.append(f"{n}: {status} @ {full_url}")
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
            notes = f"{url} → HTTP {s}" if s else f"{url} → {err or 'Unknown error'}"
        rows.append(VerifyRow(provider=provider, scope=scope, endpoint=e["name"], ok=results[e["name"]], notes=notes))

    if not ok:
        logger.error(f"[VERIFICATION TIMEOUT] Endpoints failed within {timeout_secs}s (base_url={base_url})")
    return ok, rows
