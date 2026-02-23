#!/usr/bin/env python3
"""
Diagnose AWS authentication used during deploy/teardown.

Run from repo root with .env loaded (orchestrator does this automatically).
Answers: How do we authenticate? What credential source does each component use?

Usage:
  python tools/aws/diagnose_auth.py
"""
import os
import subprocess
import sys

# Load .env so we see what deploy sees
from tools.cloud_shared.env import load_dotenv

load_dotenv()


def _run(cmd: list[str], capture: bool = True) -> tuple[int, str, str]:
    env = os.environ.copy()
    r = subprocess.run(cmd, capture_output=capture, text=True, env=env, timeout=15)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def main() -> None:
    print("=" * 60)
    print("AWS AUTH DIAGNOSTIC (what deploy/teardown use)")
    print("=" * 60)

    # 1. Env vars (masked)
    profile = os.environ.get("AWS_PROFILE", "")
    admin_key = os.environ.get("AWS_ADMIN_ACCESS_KEY_ID", "")
    admin_secret = os.environ.get("AWS_ADMIN_SECRET_ACCESS_KEY", "")
    use_profile = os.environ.get("FRU_AWS_USE_PROFILE", "")

    print("\n1. ENV VARS (from .env / shell)")
    print(f"   AWS_PROFILE           = {profile or '(not set)'}")
    print(f"   AWS_ADMIN_ACCESS_KEY_ID = {'***' + admin_key[-4:] if admin_key else '(not set)'}")
    print(f"   AWS_ADMIN_SECRET_ACCESS_KEY = {'***' if admin_secret else '(not set)'}")
    print(f"   FRU_AWS_USE_PROFILE   = {use_profile or '(not set)'}")

    # 2. Profile test
    print("\n2. PROFILE TEST (aws sts get-caller-identity --profile admin)")
    if profile:
        code, out, err = _run(["aws", "sts", "get-caller-identity", "--profile", profile])
        if code == 0:
            print(f"   OK: {out.strip()}")
        else:
            print(f"   FAIL: {err.strip() or out.strip()}")
    else:
        print("   (skipped: AWS_PROFILE not set)")

    # 3. Explicit keys test (what terra_runner passes to tofu)
    print("\n3. EXPLICIT KEYS TEST (what Terraform/tofu would use)")
    if admin_key and admin_secret:
        env = os.environ.copy()
        env["AWS_ACCESS_KEY_ID"] = admin_key
        env["AWS_SECRET_ACCESS_KEY"] = admin_secret
        env.pop("AWS_PROFILE", None)  # avoid profile override
        r = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        if r.returncode == 0:
            print(f"   OK (AWS_ADMIN_*): {r.stdout.strip()}")
        else:
            print(f"   FAIL: {r.stderr.strip() or r.stdout.strip()}")
    else:
        print("   (skipped: AWS_ADMIN_* not set)")

    # 4. Credential source used by terra_runner
    print("\n4. TERRA_RUNNER BEHAVIOR (what tofu subprocess gets)")
    if use_profile.lower() in ("1", "true", "yes") or (profile and not (admin_key and admin_secret)):
        print("   Uses: AWS_PROFILE (profile from ~/.aws/credentials)")
        print("   Reason: FRU_AWS_USE_PROFILE set, or profile set without AWS_ADMIN_*")
    elif profile and admin_key and admin_secret:
        print("   Uses: AWS_ADMIN_* (explicit keys from .env)")
        print("   Reason: Both profile and AWS_ADMIN_* set -> explicit keys take precedence")
        print("   NOTE: If .env keys are stale/rotated, deploy will fail with AuthFailure.")
        print("   FIX: Set FRU_AWS_USE_PROFILE=true to prefer profile over .env keys.")
    elif admin_key and admin_secret:
        print("   Uses: AWS_ADMIN_* (explicit keys from .env)")
    else:
        print("   Uses: default credential chain (profile if set, else credentials file)")

    # 5. Config summary
    print("\n5. RECOMMENDATION")
    if profile and admin_key and admin_secret:
        print("   Add to .env: FRU_AWS_USE_PROFILE=true")
        print("   This makes deploy use your profile (~/.aws/credentials) instead of .env keys.")
        print("   Prevents AuthFailure when .env keys are rotated but profile is current.")
    else:
        print("   Current setup is fine. Ensure AWS_PROFILE or AWS_ADMIN_* are valid.")

    print("\n" + "=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
