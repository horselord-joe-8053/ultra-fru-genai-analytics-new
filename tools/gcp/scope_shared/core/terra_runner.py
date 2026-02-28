"""Shared runner for Terraform/OpenTofu on GCP (reference: tools/aws/scope_shared/core/terra_runner.py)."""
import json
import os
import subprocess
import shlex
import tempfile
from pathlib import Path

# Temp file for GOOGLE_APPLICATION_CREDENTIALS_JSON (tofu needs file path, not inline JSON)
_creds_file: Path | None = None


def _ensure_creds_file():
    """If GOOGLE_APPLICATION_CREDENTIALS_JSON is set, write to temp file and set GOOGLE_APPLICATION_CREDENTIALS."""
    global _creds_file
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds_path and Path(creds_path).is_file():
        return
    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    if not creds_json:
        return
    try:
        json.loads(creds_json)  # validate
    except (json.JSONDecodeError, TypeError):
        return
    fd, path = tempfile.mkstemp(suffix=".json", prefix="gcp_creds_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(creds_json)
        _creds_file = Path(path)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
    except Exception:
        os.close(fd)
        Path(path).unlink(missing_ok=True)
        raise


def _shared_terra_data_dir():
    if os.environ.get("TF_DATA_DIR"):
        return os.environ["TF_DATA_DIR"]
    root = os.environ.get("REPO_ROOT") or os.getcwd()
    return os.path.join(root, "tofu_data")


def ensure_shared_terra_env():
    shared = os.path.abspath(_shared_terra_data_dir())
    os.environ["TF_DATA_DIR"] = shared


def get_terra_env(region: str | None = None, extra: dict | None = None):
    """Env for Terraform/OpenTofu subprocesses. Sets GOOGLE_APPLICATION_CREDENTIALS, CLOUD_REGION."""
    _ensure_creds_file()  # tofu GCS backend needs file path, not inline JSON
    ensure_shared_terra_env()
    env = os.environ.copy()
    env["TF_DATA_DIR"] = os.path.abspath(_shared_terra_data_dir())
    # Resolve relative GOOGLE_APPLICATION_CREDENTIALS to absolute; tofu runs with cwd=stack_dir
    creds = env.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if creds and not os.path.isabs(creds):
        root = os.environ.get("REPO_ROOT") or os.getcwd()
        abs_creds = os.path.abspath(os.path.join(root, creds))
        if Path(abs_creds).is_file():
            env["GOOGLE_APPLICATION_CREDENTIALS"] = abs_creds
    if region:
        env["CLOUD_REGION"] = region
        env["GCP_REGION"] = region
        env["TF_VAR_gcp_region"] = region
    if extra:
        env.update(extra)
    return env


def run(cmd, cwd=None, check=False):
    print(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, env=get_terra_env())


def terra_capture(cmd, cwd=None, region: str | None = None):
    """Run terra/tofu with capture_output=True."""
    exe = os.getenv("FRU_TF_BIN", "tofu")
    if cmd[0] in ["init", "plan", "apply", "destroy", "output", "import"]:
        if "-lock=false" not in cmd and cmd[0] != "import":
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return subprocess.run(
        [exe] + cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=get_terra_env(region),
    )


def terra(cmd, cwd=None, check=False):
    """Run Terraform/OpenTofu command."""
    exe = os.getenv("FRU_TF_BIN", "tofu")
    if cmd[0] in ["init", "plan", "apply", "destroy", "output"]:
        if "-lock=false" not in cmd:
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return run([exe] + cmd, cwd=cwd, check=check)
