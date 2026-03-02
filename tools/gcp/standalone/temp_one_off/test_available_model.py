#!/usr/bin/env python3
"""
Temporary one-off: Quick test if Claude model IDs work (no full deploy).
Tests all 4 candidate models with well-formatted logging and final summary.

Usage:
  python tools/gcp/standalone/temp_one_off/test_available_model.py

Requires: CLAUDE_API_KEY in .env; CLOUD_PROVIDER=gcp, GCP_LLM_PROVIDER=claude (or defaults).
"""
import os
import sys

# Project root for imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(repo_root, "core_app"))

from dotenv import load_dotenv

load_dotenv(os.path.join(repo_root, ".env"))

# Ensure GCP + Claude path
os.environ.setdefault("CLOUD_PROVIDER", "gcp")
os.environ.setdefault("GCP_LLM_PROVIDER", "claude")

MODELS = [
    "claude-haiku-4-5",
    "claude-3-haiku-20240307",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
]


def test_one(client, model: str) -> tuple[str, str, float]:
    """Run one completion. Returns (status, response_text, duration_sec)."""
    import time
    t0 = time.perf_counter()
    try:
        r = client.complete("You are helpful.", "Say OK in one word.")
        text = r.get("text", "")
        ok = "ok" in text.lower()
        elapsed = time.perf_counter() - t0
        return ("SUCCESS" if ok else "UNEXPECTED", text.strip() or "(empty)", elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        err = str(e)[:80]
        return ("FAIL", err, elapsed)


def main():
    from backend.env_utils.cloud_shared.client_factory import create_llm_client

    print("=" * 60)
    print("  Model availability test (1 call per model)")
    print("=" * 60)

    results = []
    for i, model in enumerate(MODELS, 1):
        print(f"\n[{i}/{len(MODELS)}] {model}")
        print("-" * 50)
        os.environ["CLAUDE_MODEL"] = model
        client = create_llm_client()
        actual = getattr(client, "model", "N/A")
        print(f"  Client model: {actual}")

        status, text, elapsed = test_one(client, model)
        results.append((model, status, text, elapsed))

        print(f"  Response: {text!r}")
        print(f"  Status:  {status} ({elapsed:.2f}s)")

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    print(f"  {'Model':<35} {'Status':<12} {'Time':<10} Response")
    print("-" * 60)
    for model, status, text, elapsed in results:
        resp_preview = (text[:30] + "..") if len(text) > 30 else text
        print(f"  {model:<35} {status:<12} {elapsed:>6.2f}s    {resp_preview}")
    print("-" * 60)
    ok_count = sum(1 for _, s, _, _ in results if s == "SUCCESS")
    print(f"  Passed: {ok_count}/{len(MODELS)}")
    print("=" * 60)
    sys.exit(0 if ok_count == len(MODELS) else 1)


if __name__ == "__main__":
    main()
