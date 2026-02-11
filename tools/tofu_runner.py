
"""Shared runner with common flags and clear logs."""
import subprocess, os, shlex

def _shared_tofu_data_dir():
    """Single shared dir for OpenTofu data (providers, etc.) so we don't duplicate per stack."""
    if os.environ.get("TF_DATA_DIR"):
        return os.environ["TF_DATA_DIR"]
    # Default: repo root / tofu_data (run tools from repo root)
    root = os.environ.get("REPO_ROOT") or os.getcwd()
    return os.path.join(root, "tofu_data")

def ensure_shared_tofu_env():
    """Ensure TF_DATA_DIR is set so any tofu subprocess uses the shared provider cache."""
    shared = os.path.abspath(_shared_tofu_data_dir())
    os.environ["TF_DATA_DIR"] = shared

def get_tofu_env():
    """Env for tofu subprocesses. Needed when calling subprocess.run(..., capture_output=True) directly:
    must pass env= explicitly. Sets TF_DATA_DIR (shared provider cache) and maps AWS_ADMIN_* to
    AWS_ACCESS_KEY_ID/SECRET so tofu uses admin credentials."""
    ensure_shared_tofu_env()
    shared = os.path.abspath(_shared_tofu_data_dir())
    env = os.environ.copy()
    env["TF_DATA_DIR"] = shared
    if env.get("AWS_ADMIN_ACCESS_KEY_ID"):
        env["AWS_ACCESS_KEY_ID"] = env["AWS_ADMIN_ACCESS_KEY_ID"]
    if env.get("AWS_ADMIN_SECRET_ACCESS_KEY"):
        env["AWS_SECRET_ACCESS_KEY"] = env["AWS_ADMIN_SECRET_ACCESS_KEY"]
    return env

def run(cmd, cwd=None, check=False):
    print(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, env=get_tofu_env())

def tofu(cmd, cwd=None, check=False):
    exe = os.getenv("FRU_TF_BIN","tofu")
    # Add -lock=false for commands that support it to bypass TCC write blocks
    if cmd[0] in ["init", "plan", "apply", "destroy", "output"]:
        if "-lock=false" not in cmd:
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return run([exe] + cmd, cwd=cwd, check=check)
