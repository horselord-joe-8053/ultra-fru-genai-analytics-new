#!/usr/bin/env python3
"""
Local deployment verification. Aligned with AWS/GCP verify_all_deploy.

Uses tools.cloud_shared.verify (verify_api_endpoints, verify_llm_client, verify_summary).
Ports per scope from config/local/local_deploy_config.yaml (LOCAL_DEPLOY_CONFIG).
--scope kube | nonkube | all (default from memo .fru_local_scope if present).

Usage:
  python orchestrator.py verify --provider local --scope kube
  python tools/local/scope_shared/verify/verify_all_deploy.py --scope nonkube

Prerequisite: API running (e.g. via deploy --provider local which starts it).
"""
import argparse
import os
import sys
import time

# Allow running as script without PYTHONPATH
_verify_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _verify_root not in sys.path:
    sys.path.insert(0, _verify_root)

# Force immediate output so orchestrator subprocess doesn't appear stuck
print("verify_all_deploy: starting...", flush=True)

import requests

from tools.cloud_shared.env import load_dotenv
load_dotenv()

from tools.cloud_shared.logging import logger
from tools.cloud_shared.verify.verify_api_endpoints import verify_api_endpoints
from tools.cloud_shared.verify.verify_llm_client import verify_llm_client
from tools.cloud_shared.verify.verify_summary import VerifyRow, print_verify_summary
from tools.cloud_shared.verify.verify_csv import get_total_rec_from_csv
from tools.local.scope_shared.local_deploy_config import get_memo_dir, get_ports_for_scope

print("verify_all_deploy: imports done, entering main()", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], help="Scope to verify (default: from memo or nonkube)")
    args, _ = ap.parse_known_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    memo_dir = get_memo_dir()
    scope = args.scope
    if not scope:
        scope_file = os.path.join(memo_dir, ".fru_local_scope")
        if os.path.exists(scope_file):
            with open(scope_file) as f:
                scope = f.read().strip() or "nonkube"
        else:
            scope = "nonkube"
    ports = get_ports_for_scope(scope)
    base_url = os.environ.get("LOCAL_API_URL") or f"http://localhost:{ports['api_port']}"
    if not base_url.startswith("http"):
        base_url = f"http://{base_url}"
    frontend_url = os.environ.get("LOCAL_FRONTEND_URL") or f"http://localhost:{ports['frontend_port']}"
    frontend_url = frontend_url.rstrip("/")

    total_rec = get_total_rec_from_csv()
    verify_start = time.time()

    logger.operation_start("Verify", "local", os.getenv("FRU_ENV", "dev"), "local")
    logger.step(f"Full Verification Interface (local, scope={scope}, total_rec from CSV: {total_rec})")
    logger.phase_start(1, 2, "Endpoints (local)")

    ok, rows = verify_api_endpoints(
        base_url=base_url,
        total_rec=total_rec,
        scope="local",
        provider="local",
        skip_frontend=True,
    )

    # Frontend (local): port from config for this scope
    frontend_notes = frontend_url
    try:
        r = requests.get(frontend_url + "/", timeout=10)
        frontend_ok = r.status_code == 200 and "<html" in (r.text or "").lower()
        if not frontend_ok:
            frontend_notes = f"HTTP {r.status_code}"
    except Exception as ex:
        frontend_ok = False
        frontend_notes = str(ex)
        logger.warning(f"Frontend (local) check failed: {ex}")
    rows.append(VerifyRow(provider="local", scope="local", endpoint="Frontend (local)", ok=frontend_ok, notes=frontend_notes))
    if not frontend_ok:
        ok = False

    if not ok:
        logger.error("[VERIFICATION FAILED] API endpoints are not responding correctly")
        print_verify_summary(rows, os.getenv("FRU_ENV", "dev"), total_rec)
        logger.operation_end("Verify", "local", os.getenv("FRU_ENV", "dev"), "local", int(time.time() - verify_start), ok=False)
        sys.exit(1)

    logger.phase_end(1, 2, "Endpoints (local)", int(time.time() - verify_start))

    # LLM client (optional for local; same as AWS/GCP)
    phase_start = time.time()
    logger.phase_start(2, 2, "LLM client")
    llm_ok, llm_rows = verify_llm_client()
    rows.extend(llm_rows)
    logger.phase_end(2, 2, "LLM client", int(time.time() - phase_start))

    if not llm_ok:
        logger.error("[VERIFICATION FAILED] LLM client failed")
        print_verify_summary(rows, os.getenv("FRU_ENV", "dev"), total_rec)
        logger.operation_end("Verify", "local", os.getenv("FRU_ENV", "dev"), "local", int(time.time() - verify_start), ok=False)
        sys.exit(1)

    print_verify_summary(rows, os.getenv("FRU_ENV", "dev"), total_rec)
    verify_dur = int(time.time() - verify_start)
    logger.operation_end("Verify", "local", os.getenv("FRU_ENV", "dev"), "local", verify_dur, ok=True)
    logger.success("FULL VERIFICATION: SUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
