"""
Shared LLM client verification: create client and append one row.
Used by AWS and GCP verify scripts.
This verifies local LLM client use (runs on verify machine), so provider is always "local".
"""
import os
import sys

from tools.cloud_shared.verify.verify_summary import VerifyRow


def verify_llm_client() -> tuple[bool, list[VerifyRow]]:
    """
    Verify LLM client can be instantiated (local use). Returns (ok, rows).
    Provider is always "local" — this test verifies local LLM client connectivity.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    core_app = os.path.join(repo_root, "core_app")
    if core_app not in sys.path:
        sys.path.insert(0, core_app)

    try:
        from backend.env_utils.cloud_shared.client_factory import create_llm_client
        client = create_llm_client()
        notes = type(client).__name__
        rows = [VerifyRow(provider="local", scope="shared", endpoint="LLM client", ok=True, notes=notes)]
        return True, rows
    except Exception as e:
        rows = [VerifyRow(provider="local", scope="shared", endpoint="LLM client", ok=False, notes=str(e))]
        return False, rows
