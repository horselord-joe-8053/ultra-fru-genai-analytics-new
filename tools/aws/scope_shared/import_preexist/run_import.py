"""
Import pre-existing resources into Terraform state (import_preexist).

Run before apply when state/reality may be out of sync (e.g. after brutal removal).
Safe to run always: non-existent and already-in-state are skipped.

Usage:
  python tools/aws/scope_shared/import_preexist/run_import.py --scope nonkube --env dev
  python tools/aws/scope_shared/import_preexist/run_import.py --scope all --env dev

Reference: legacy orchestration/terraform/import_preexist/
"""
import argparse
import os
import sys

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.core.backend import resolve_region
from tools.cloud_shared.logging import logger
from tools.aws.scope_shared.core.terra_init import init_stack
from tools.aws.scope_shared.core.terra_var_handling import get_base_vars
from tools.aws.scope_shared.import_preexist.nonkube import run_import_nonkube
from tools.aws.scope_shared.import_preexist.kube import run_import_kube

load_dotenv()

NONKUBE_STACK = "infra_terraform/live_deploy/aws/nonkube"
KUBE_STACK = "infra_terraform/live_deploy/aws/kube"


def main():
    ap = argparse.ArgumentParser(
        description="Import pre-existing AWS resources into Terraform state"
    )
    ap.add_argument("--scope", choices=["kube", "nonkube", "all"], required=True)
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    if args.region:
        os.environ["CLOUD_REGION"] = args.region
    region = resolve_region(args.region)
    prefix = os.getenv("FRU_PREFIX", "fru")

    logger.info(f"Import pre-existing resources: scope={args.scope} env={args.env} region={region}")

    get_base_vars(args.env, region)
    total_failed = 0

    if args.scope in ("nonkube", "all"):
        init_stack(NONKUBE_STACK, args.env, region)
        total_failed += run_import_nonkube(NONKUBE_STACK, args.env, region, prefix)

    if args.scope in ("kube", "all"):
        init_stack(KUBE_STACK, args.env, region)
        eks_cluster_name = os.getenv("EKS_CLUSTER_NAME") or f"{prefix}-{args.env}-eks"
        total_failed += run_import_kube(
            KUBE_STACK, args.env, region, prefix, eks_cluster_name=eks_cluster_name
        )

    if total_failed > 0:
        sys.exit(1)
    logger.success("Import complete.")


if __name__ == "__main__":
    main()
