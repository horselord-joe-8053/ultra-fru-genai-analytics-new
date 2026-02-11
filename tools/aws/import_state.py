
"""
Import a single resource into state.

Usage:
  python tools/aws/import_state.py <stack_dir> <addr> <id>
"""
import os, subprocess, sys
stack, addr, rid = sys.argv[1:4]
from tools.tofu_runner import ensure_shared_tofu_env
ensure_shared_tofu_env()
subprocess.run([os.getenv("FRU_TF_BIN","tofu"),"import",addr,rid], cwd=stack, check=False)
