
"""
Import a single resource into state.

Usage:
  python tools/aws/import_state.py <stack_dir> <addr> <id>
"""
import subprocess, sys
stack, addr, rid = sys.argv[1:4]
subprocess.run([os.getenv("FRU_TF_BIN","tofu"),"import",addr,rid], cwd=stack, check=False)
