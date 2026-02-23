
"""Shared runner for Terraform/OpenTofu with common flags and clear logs."""
import subprocess
import os
import shlex


def _shared_terra_data_dir():
    """Single shared dir for Terraform/OpenTofu data (providers, etc.) so we don't duplicate per stack."""
    if os.environ.get("TF_DATA_DIR"):
        return os.environ["TF_DATA_DIR"]
    # Default: repo root / tofu_data (run tools from repo root)
    root = os.environ.get("REPO_ROOT") or os.getcwd()
    return os.path.join(root, "tofu_data")


def ensure_shared_terra_env():
    """Ensure TF_DATA_DIR is set so any Terraform/OpenTofu subprocess uses the shared provider cache."""
    shared = os.path.abspath(_shared_terra_data_dir())
    os.environ["TF_DATA_DIR"] = shared


def _use_profile_over_explicit_keys(env: dict) -> bool:
    """Prefer AWS_PROFILE over AWS_ADMIN_* when FRU_AWS_USE_PROFILE=true.
    Prevents AuthFailure when .env keys are stale/rotated but profile is current."""
    use_profile = env.get("FRU_AWS_USE_PROFILE", "").strip().lower()
    if use_profile in ("1", "true", "yes"):
        return True
    return False


def get_terra_env(region: str | None = None, extra: dict | None = None):
    """Env for Terraform/OpenTofu subprocesses. Needed when calling subprocess.run(..., capture_output=True) directly:
    must pass env= explicitly. Sets TF_DATA_DIR (shared provider cache) and maps AWS_ADMIN_* to
    AWS_ACCESS_KEY_ID/SECRET so the binary uses admin credentials.
    If region is provided, sets CLOUD_REGION (Terraform gets region via TF_VAR_aws_region).
    extra: optional dict of additional env vars (e.g. TF_VAR_s3_bucket_region for S3 provider alias).

    Credential precedence: When FRU_AWS_USE_PROFILE=true, use AWS_PROFILE (profile from ~/.aws/credentials)
    instead of AWS_ADMIN_* from .env. This avoids AuthFailure when .env keys are rotated but profile is current."""
    ensure_shared_terra_env()
    shared = os.path.abspath(_shared_terra_data_dir())
    env = os.environ.copy()
    env["TF_DATA_DIR"] = shared
    if region:
        env["CLOUD_REGION"] = region
        env["AWS_REGION"] = region
        env["AWS_DEFAULT_REGION"] = region
        env["TF_VAR_aws_region"] = region  # provider region (critical for S3 import)
    if extra:
        env.update(extra)
    # Use profile when explicitly requested; otherwise use AWS_ADMIN_* when set
    if _use_profile_over_explicit_keys(env):
        # Don't set AWS_ACCESS_KEY_ID/SECRET so the provider uses AWS_PROFILE.
        # Explicitly unset any inherited keys so profile takes precedence.
        env.pop("AWS_ACCESS_KEY_ID", None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
    else:
        if env.get("AWS_ADMIN_ACCESS_KEY_ID"):
            env["AWS_ACCESS_KEY_ID"] = env["AWS_ADMIN_ACCESS_KEY_ID"]
        if env.get("AWS_ADMIN_SECRET_ACCESS_KEY"):
            env["AWS_SECRET_ACCESS_KEY"] = env["AWS_ADMIN_SECRET_ACCESS_KEY"]
    return env


def run(cmd, cwd=None, check=False):
    print(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, env=get_terra_env())


def terra_capture(cmd, cwd=None, region: str | None = None):
    """Run terra/tofu with capture_output=True. Returns CompletedProcess.
    Wrapped with auth_retry (auth_retry.py): on SignatureDoesNotMatch, AuthFailure,
    InvalidSignatureException, sync clock via NTP and retry. See auth_retry.py origin."""
    from tools.aws.scope_shared.core.auth_retry import run_with_auth_retry

    exe = os.getenv("FRU_TF_BIN", "tofu")
    if cmd[0] in ["init", "plan", "apply", "destroy", "output", "import"]:
        if "-lock=false" not in cmd and cmd[0] != "import":
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return run_with_auth_retry(
        lambda: subprocess.run(
            [exe] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=get_terra_env(region),
        )
    )


def terra(cmd, cwd=None, check=False):
    """Run Terraform/OpenTofu command. Binary from FRU_TF_BIN env (default: tofu)."""
    exe = os.getenv("FRU_TF_BIN", "tofu")
    # Add -lock=false for commands that support it to bypass TCC write blocks
    if cmd[0] in ["init", "plan", "apply", "destroy", "output"]:
        if "-lock=false" not in cmd:
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return run([exe] + cmd, cwd=cwd, check=check)
