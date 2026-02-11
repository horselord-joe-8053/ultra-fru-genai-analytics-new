#!/bin/bash
# Run terraform init -upgrade -reconfigure with S3 backend config from .env.
# Usage: from repo root: ./deploy-aws/shared/nondurable/init_with_backend.sh
#        or from here:   ./init_with_backend.sh (script finds repo root)

set -e
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
: "${AWS_REGION:=us-east-1}"
: "${TF_STATE_PREFIX:=$FRU_PREFIX}"
: "${TF_STATE_PREFIX:=fru}"
: "${FRU_ENV:=$ENVIRONMENT}"
: "${FRU_ENV:=dev}"

KEY="${TF_STATE_PREFIX}/${FRU_ENV}/aws-shared-nondurable.tfstate"
BACKEND_CFG=(
  -backend-config="bucket=$TF_STATE_BUCKET"
  -backend-config="key=$KEY"
  -backend-config="region=$AWS_REGION"
  -backend-config=encrypt=true
  -backend-config=use_lockfile=true
)
if [ -n "${TF_STATE_LOCK_TABLE}${TF_LOCK_TABLE}" ]; then
  TBL="${TF_STATE_LOCK_TABLE:-$TF_LOCK_TABLE}"
  BACKEND_CFG+=( -backend-config="dynamodb_table=$TBL" )
fi

cd "$SCRIPT_DIR"
export TF_DATA_DIR="$REPO_ROOT/tofu_data"
exec "${FRU_TF_BIN:-tofu}" init -upgrade -reconfigure "${BACKEND_CFG[@]}"
