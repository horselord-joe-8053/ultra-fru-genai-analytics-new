#!/usr/bin/env python3
"""
Local doctor: preflight checks for local deploy.

Usage:
  python orchestrator.py doctor --provider local
"""
import os
import subprocess
import sys

# Allow importing from project root (core_app, tools)
_here = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger

load_dotenv()


def _check_claude_model() -> list[str]:
    """Require CLAUDE_MODEL when using Claude; validate model via API (fail-fast)."""
    errs = []
    api_key = (os.environ.get("CLAUDE_API_KEY") or "").strip()
    if not api_key:
        return errs  # No Claude key → skip model check

    try:
        from core_app.backend.env_utils.cloud_shared.model_config import require_claude_model
        model = require_claude_model()
    except ValueError as e:
        errs.append(str(e))
        return errs

    # Validate model: call Anthropic API with minimal request (fail-fast on 404/auth)
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        client.messages.create(
            model=model,
            max_tokens=10,
            system="You are a test.",
            messages=[{"role": "user", "content": "Say OK"}],
        )
    except Exception as e:
        msg = str(e).lower()
        if "404" in msg or "not_found" in msg or "model" in msg:
            errs.append(
                f"CLAUDE_MODEL={model} is invalid or not found. Check the model id in .env and your API access."
            )
        else:
            errs.append(f"Claude API check failed: {e}")
    return errs


def main() -> int:
    logger.step("Local doctor (preflight)")

    errors = []

    # Docker
    r = subprocess.run(["docker", "info"], capture_output=True)
    if r.returncode != 0:
        errors.append("Docker not running or not installed")

    # Required env
    for var in ["PGPASSWORD", "OPENAI_API_KEY"]:
        if not os.environ.get(var):
            errors.append(f"{var} not set (check .env)")

    # CLAUDE_MODEL required when CLAUDE_API_KEY set; validate model via API
    errors.extend(_check_claude_model())

    # Optional but recommended if no Claude
    if not os.environ.get("CLAUDE_API_KEY") and not os.environ.get("GOOGLE_AI_API_KEY"):
        logger.warning("No CLAUDE_API_KEY or GOOGLE_AI_API_KEY; set CLOUD_PROVIDER=local and CLAUDE_API_KEY for /query")

    # CSV exists
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    csv_path = os.path.join(project_root, "core_app", "data", "raw", "fridge_sales_with_rating.csv")
    if not os.path.exists(csv_path):
        errors.append(f"CSV not found: {csv_path}")

    if errors:
        for e in errors:
            logger.error(e)
        return 1

    logger.success("Preflight OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
