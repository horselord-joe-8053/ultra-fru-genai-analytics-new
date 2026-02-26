#!/bin/bash
#
# init_terra_upgrade_reconfigure.sh — Run OpenTofu/Terraform init -upgrade -reconfigure
# with S3 backend config so the backend does not prompt for input.
#
# **What it's for:** When you run `tofu init -upgrade -reconfigure` (or terraform)
# directly in a stack directory, the backend block has no config in HCL, so Terraform
# prompts for bucket/key/region and fails in non-interactive use. This script loads
# backend config from .env and runs init with -backend-config so init succeeds
# without prompts. Use it when you want to init a single stack by hand (e.g. to run
# tofu plan locally) without going through the full deploy.
#
# **How to run:** From repo root only. Requires .env (or .env.fru) with at least
# TF_STATE_BUCKET, CLOUD_REGION; optional TF_STATE_PREFIX/PROJ_PREFIX/FRU_PREFIX, FRU_ENV,
# TF_LOCK_TABLE/TF_STATE_LOCK_TABLE.
#
#   ./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh <stack_dir> [env]
#
# Examples:
#   ./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh infra_terraform/live_deploy/aws/scope_shared/nondurable
#   ./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh infra_terraform/live_deploy/aws/scope_shared/durable dev
#   ./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh infra_terraform/live_deploy/aws/nonkube dev
#
# Then you can run tofu plan / apply / destroy from that stack directory (with
# TF_DATA_DIR set to repo root tofu_data if you use the project's convention).
#
set -e
if [ $# -lt 1 ]; then
  echo "Usage: $0 <stack_dir> [env]" >&2
  echo "  stack_dir  e.g. infra_terraform/live_deploy/aws/scope_shared/nondurable or infra_terraform/live_deploy/aws/scope_shared/durable" >&2
  echo "  env        default: FRU_ENV or dev" >&2
  echo "Run from repo root. Requires .env with TF_STATE_BUCKET, CLOUD_REGION." >&2
  exit 1
fi

STACK_DIR="$1"
ENV="${2:-${FRU_ENV:-${ENVIRONMENT:-dev}}}"

# Repo root: assume script lives in tools/aws/scope_shared/utils/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# Load .env or .env.fru
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
elif [ -f .env.fru ]; then
  set -a
  # shellcheck source=/dev/null
  source .env.fru
  set +a
fi

: "${TF_STATE_BUCKET:?Set TF_STATE_BUCKET in .env}"
: "${CLOUD_REGION:=us-east-1}"
PREFIX="${TF_STATE_PREFIX:-${PROJ_PREFIX:-${FRU_PREFIX:-fru}}}"

# Match backend.py: stack_id_from_dir (cloud=aws from script location; strip first path component)
# e.g. infra_terraform/live_deploy/aws/scope_shared/durable -> aws-shared-durable
PARTS="$(echo "$STACK_DIR" | sed 's|/*$||' | tr '/' '\n')"
REST="$(echo "$PARTS" | tail -n +2 | tr '\n' '-')"
STACK_ID="aws-${REST%-}"
KEY="${PREFIX}/${ENV}/${STACK_ID}.tfstate"

BACKEND_CFG=(
  -backend-config="bucket=$TF_STATE_BUCKET"
  -backend-config="key=$KEY"
  -backend-config="region=$CLOUD_REGION"
  -backend-config=encrypt=true
  -backend-config=use_lockfile=true
)
if [ -n "${TF_STATE_LOCK_TABLE}${TF_LOCK_TABLE}" ]; then
  TBL="${TF_STATE_LOCK_TABLE:-$TF_LOCK_TABLE}"
  BACKEND_CFG+=( -backend-config="dynamodb_table=$TBL" )
fi

cd "$REPO_ROOT/$STACK_DIR"
export TF_DATA_DIR="${REPO_ROOT}/tofu_data"
exec "${FRU_TF_BIN:-tofu}" init -upgrade -reconfigure "${BACKEND_CFG[@]}"
