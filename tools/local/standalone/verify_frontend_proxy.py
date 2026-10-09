#!/usr/bin/env python3
"""
Verify which API each local frontend (5173, 5174) is proxying to.

Requests http://localhost:<frontend_port>/version and checks:
  - scope: 5173 (kube) must get scope "kube"; 5174 (nonkube) must get scope "nonkube".
  - api_port (if present): 5173 must not get 5001 (nonkube); 5174 must get 5001.
  - /model-catalog must return JSON with stacks[] (nginx must proxy, not SPA index.html).

Usage:
  python tools/local/standalone/verify_frontend_proxy.py

Expected:
  - Frontend 5173 (kube)   -> scope "kube"   (API 30080)
  - Frontend 5174 (nonkube) -> scope "nonkube" (API 5001)
"""
import os
import sys

_here = os.path.abspath(os.path.dirname(__file__))
# tools/local/standalone -> project root (3 levels up)
_project_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.cloud_shared.env import load_dotenv
load_dotenv()

import requests
from tools.local.scope_shared.local_deploy_config import get_ports_for_scope


def _check_model_catalog(base_url: str, label: str) -> bool:
    """GET /model-catalog must be JSON (not nginx SPA fallback)."""
    url = f"{base_url.rstrip('/')}/model-catalog"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        if "json" not in ct:
            print(
                f"FAIL  {label}: /model-catalog content-type={ct!r} — "
                "rebuild fru-api:local and restart kube/nonkube API (nginx route missing?)"
            )
            return False
        data = r.json()
        if not isinstance(data.get("stacks"), list):
            print(f"FAIL  {label}: /model-catalog JSON missing stacks[] — rebuild/restart API")
            return False
        print(f"OK    {label} -> /model-catalog stacks={len(data['stacks'])}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"SKIP  {label}: /model-catalog not reachable")
        return True
    except Exception as e:
        print(f"ERROR {label}: /model-catalog — {e}")
        return False


def main() -> int:
    kube_ports = get_ports_for_scope("kube")
    nonkube_ports = get_ports_for_scope("nonkube")
    checks = [
        (kube_ports["frontend_port"], "kube"),
        (nonkube_ports["frontend_port"], "nonkube"),
    ]
    ok = True
    for frontend_port, expected_scope in checks:
        url = f"http://localhost:{frontend_port}/version"
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            data = r.json()
            actual_scope = data.get("scope")
            actual_api_port = data.get("api_port")
            # Prefer scope (DEPLOY_SCOPE) to identify backend; fall back to api_port if scope missing
            if expected_scope == "kube":
                if actual_scope == "nonkube" or (actual_api_port is not None and actual_api_port == nonkube_ports["api_port"]):
                    print(f"FAIL  Frontend {frontend_port} (kube): proxying to nonkube API (scope={actual_scope!r}, api_port={actual_api_port}) — should proxy to kube ({kube_ports['api_port']})")
                    ok = False
                elif actual_scope == "kube":
                    print(f"OK    Frontend {frontend_port} (kube) -> scope=kube, api_port={actual_api_port}")
                else:
                    print(f"??    Frontend {frontend_port} (kube): scope={actual_scope!r}, api_port={actual_api_port} (set DEPLOY_SCOPE=kube on kube API to verify)")
            else:
                if actual_scope == "kube":
                    print(f"FAIL  Frontend {frontend_port} (nonkube): proxying to kube API (scope={actual_scope!r}) — should proxy to nonkube ({nonkube_ports['api_port']})")
                    ok = False
                elif actual_scope == "nonkube" or actual_api_port == nonkube_ports["api_port"]:
                    print(f"OK    Frontend {frontend_port} (nonkube) -> scope={actual_scope!r}, api_port={actual_api_port}")
                else:
                    print(f"??    Frontend {frontend_port} (nonkube): scope={actual_scope!r}, api_port={actual_api_port} (set DEPLOY_SCOPE=nonkube on nonkube API to verify)")
        except requests.exceptions.ConnectionError:
            print(f"SKIP  Frontend {frontend_port} ({expected_scope}): not running or not reachable")
        except Exception as e:
            print(f"ERROR Frontend {frontend_port} ({expected_scope}): {e}")
            ok = False

    print("")
    print("Model catalog (JSON via proxy):")
    for frontend_port, expected_scope in checks:
        if not _check_model_catalog(f"http://localhost:{frontend_port}", f"Frontend {frontend_port} ({expected_scope})"):
            ok = False

    print("")
    print("Model catalog (direct API ports):")
    for scope, ports in (("kube", kube_ports), ("nonkube", nonkube_ports)):
        if not _check_model_catalog(
            f"http://localhost:{ports['api_port']}",
            f"API {ports['api_port']} ({scope})",
        ):
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
