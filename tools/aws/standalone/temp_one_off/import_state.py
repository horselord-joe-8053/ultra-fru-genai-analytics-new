
"""
Import a single resource into state.

Usage:
  python tools/aws/standalone/temp_one_off/import_state.py <stack_dir> <addr> <id>
"""
import os, subprocess, sys
stack, addr, rid = sys.argv[1:4]
from tools.aws.scope_shared.core.terra_runner import ensure_shared_terra_env
ensure_shared_terra_env()
subprocess.run([os.getenv("FRU_TF_BIN","tofu"),"import",addr,rid], cwd=stack, check=False)
