"""
Import pre-existing AWS resources into Terraform state.

When resources exist in AWS but not in state (e.g. after brutal removal or partial
teardown), apply fails with EntityAlreadyExists. Run import before apply to adopt them.

Usage:
  - Called automatically by deploy before nonkube/kube apply
  - Called automatically by teardown before nonkube/kube destroy (state reconciliation)
  - Standalone: python tools/aws/scope_shared/import_preexist/run_import.py --scope nonkube --env dev
"""
from tools.aws.scope_shared.import_preexist.nonkube import run_import_nonkube
from tools.aws.scope_shared.import_preexist.kube import run_import_kube

__all__ = ["run_import_nonkube", "run_import_kube"]
