#!/usr/bin/env python3
"""
Local deployment verification. Aligned with AWS/GCP verify_all_deploy.

Uses tools.cloud_shared.verify (verify_api_endpoints, verify_llm_client, verify_summary).
Local: base_url from LOCAL_API_URL; API endpoints skip Frontend; separate Frontend (local)
check at LOCAL_FRONTEND_URL (default http://localhost:5173); optional LLM client check.

Usage:
  python orchestrator.py verify --provider local

Prerequisite: API running (e.g. via deploy --provider local which starts it).
"""
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

print("verify_all_deploy: imports done, entering main()", flush=True)


def main() -> int:
    # Prefer port file written by start_local (when deploy+start ran); else env
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    port_file = os.path.join(project_root, "tools", "local", "memo", ".fru_local_api_port")
    if os.path.exists(port_file):
        with open(port_file) as f:
            port = f.read().strip()
        base_url = f"http://localhost:{port}"
    else:
        base_url = os.environ.get("LOCAL_API_URL", "http://localhost:5001").rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"http://{base_url}"

    total_rec = get_total_rec_from_csv()
    verify_start = time.time()

    logger.operation_start("Verify", "local", os.getenv("FRU_ENV", "dev"), "local")
    logger.step(f"Full Verification Interface (local, total_rec from CSV: {total_rec})")
    logger.phase_start(1, 2, "Endpoints (local)")

    ok, rows = verify_api_endpoints(
        base_url=base_url,
        total_rec=total_rec,
        scope="local",
        provider="local",
        skip_frontend=True,
    )

    # Frontend (local): Vite dev server at localhost:5173 (matches cloud verify which checks Frontend)
    frontend_url = os.environ.get("LOCAL_FRONTEND_URL", "http://localhost:5173").rstrip("/")
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
