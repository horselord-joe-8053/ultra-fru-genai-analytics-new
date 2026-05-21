import os
import sys
from unittest.mock import patch

import orchestrator


def test_run_command_sets_repo_root_and_pythonpath(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_root = str(tmp_path)
    with patch.object(orchestrator, "__file__", os.path.join(fake_root, "orchestrator.py")):
        with patch("orchestrator.subprocess.run") as run:
            run.return_value.returncode = 0
            orchestrator.run_command(["python", "-c", "pass"])
    env = run.call_args.kwargs["env"]
    assert env["REPO_ROOT"] == fake_root
    assert fake_root in env["PYTHONPATH"]
    assert env["PYTHONUNBUFFERED"] == "1"
