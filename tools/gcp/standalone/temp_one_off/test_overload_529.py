#!/usr/bin/env python3
"""
Temporary one-off: Test if we can reproduce 529 overloaded_error by running
consecutive API calls with 2s interval. Tests all 4 candidate models.

Usage:
  python tools/gcp/standalone/temp_one_off/test_overload_529.py

Requires: CLAUDE_API_KEY in .env; CLOUD_PROVIDER=gcp, GCP_LLM_PROVIDER=claude (or defaults).
"""
import os
import sys
import time

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

N_RUNS = 10
INTERVAL_SEC = 2


def run_overload_test(client, model: str) -> tuple[int, int, int]:
    """Run N_RUNS consecutive calls. Returns (ok_count, err_529_count, other_err_count)."""
    results = []
    for i in range(N_RUNS):
        try:
            r = client.complete("You are helpful.", "Say OK in one word.")
            text = r.get("text", "")[:80]
            ok = "ok" in text.lower()
            status = "OK" if ok else "UNEXPECTED"
            results.append(status)
            print(f"    [{i + 1:2}/{N_RUNS}] {status}: {text!r}")
        except Exception as e:
            err = str(e)
            is_529 = "529" in err or "overloaded" in err.lower()
            status = "529" if is_529 else "ERR"
            results.append(status)
            print(f"    [{i + 1:2}/{N_RUNS}] {status}: {err[:80]}...")
        if i < N_RUNS - 1:
            time.sleep(INTERVAL_SEC)

    ok_count = sum(1 for s in results if s == "OK")
    err_529 = sum(1 for s in results if s == "529")
    other_err = sum(1 for s in results if s in ("ERR", "UNEXPECTED"))
    return ok_count, err_529, other_err


def main():
    from backend.env_utils.cloud_shared.client_factory import create_llm_client

    print("=" * 60)
    print("  Overload test (10 runs × 2s interval per model)")
    print("=" * 60)

    all_results = []
    for model_idx, model in enumerate(MODELS, 1):
        print(f"\n[{model_idx}/{len(MODELS)}] {model}")
        print("-" * 50)
        os.environ["CLAUDE_MODEL"] = model
        client = create_llm_client()
        actual = getattr(client, "model", "N/A")
        print(f"  Client model: {actual}")
        print(f"  Runs: {N_RUNS}, interval: {INTERVAL_SEC}s\n")

        ok_count, err_529, other_err = run_overload_test(client, model)

        print(f"\n  Model summary: OK={ok_count}, 529={err_529}, other={other_err}")
        all_results.append((model, ok_count, err_529, other_err))

    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    print(f"  {'Model':<35} {'OK':<6} {'529':<6} {'Other':<6} Status")
    print("-" * 60)
    for model, ok, err529, other in all_results:
        status = "PASS" if err529 == 0 else "FAIL (529)" if err529 else "FAIL (other)"
        print(f"  {model:<35} {ok:<6} {err529:<6} {other:<6} {status}")
    print("-" * 60)
    total_529 = sum(r[2] for r in all_results)
    models_ok = sum(1 for r in all_results if r[2] == 0)
    print(f"  Models with no 529: {models_ok}/{len(MODELS)}")
    print(f"  Total 529 errors: {total_529}")
    print("=" * 60)
    sys.exit(0 if total_529 == 0 else 1)


if __name__ == "__main__":
    main()
