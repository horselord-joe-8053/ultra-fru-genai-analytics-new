
"""Shared runner with common flags and clear logs."""
import subprocess, os, shlex

def run(cmd, cwd=None, check=False):
    print(f"[run] cwd={cwd} :: {' '.join(shlex.quote(x) for x in cmd)}")
    
    # Map AWS Admin credentials to standard keys if present
    env = os.environ.copy()
    if env.get("AWS_ADMIN_ACCESS_KEY_ID"):
        env["AWS_ACCESS_KEY_ID"] = env["AWS_ADMIN_ACCESS_KEY_ID"]
    if env.get("AWS_ADMIN_SECRET_ACCESS_KEY"):
        env["AWS_SECRET_ACCESS_KEY"] = env["AWS_ADMIN_SECRET_ACCESS_KEY"]
        
    return subprocess.run(cmd, cwd=cwd, check=check, env=env)

def tofu(cmd, cwd=None, check=False):
    exe = os.getenv("FRU_TF_BIN","tofu")
    # Add -lock=false for commands that support it to bypass TCC write blocks
    if cmd[0] in ["init", "plan", "apply", "destroy", "output"]:
        if "-lock=false" not in cmd:
            cmd = [cmd[0], "-lock=false"] + cmd[1:]
    return run([exe] + cmd, cwd=cwd, check=check)
