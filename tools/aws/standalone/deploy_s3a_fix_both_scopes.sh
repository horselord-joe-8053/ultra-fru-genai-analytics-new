#!/usr/bin/env bash
# Deploy S3A NumberFormatException fix to both nonkube and kube.
#
# Minimum steps: rebuild+push Spark image (shared), then re-run bootstrap for each scope.
# No Terraform, no full deploy. See WAR_STORIES_AWS.md §12.
#
# Usage:
#   ./tools/aws/standalone/deploy_s3a_fix_both_scopes.sh [--env dev] [--region us-east-2]
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

ENV="dev"
REGION="us-east-2"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV="$2"; shift 2;;
    --env=*) ENV="${1#*=}"; shift;;
    --region) REGION="$2"; shift 2;;
    --region=*) REGION="${1#*=}"; shift;;
    *) shift;;
  esac
done

export CLOUD_REGION="$REGION"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PROJECT_ROOT"
export APP_IMAGE_TAG="${APP_IMAGE_TAG:-latest}"
export SPARK_IMAGE_TAG="${SPARK_IMAGE_TAG:-latest}"
if [[ -n "$PYTHON_CMD" ]]; then
  PYTHON="$PYTHON_CMD"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

echo "=== Deploy S3A fix: env=$ENV region=$REGION ==="

echo ""
echo "[1/3] Building and pushing Spark image (shared by both scopes)..."
"$PYTHON" tools/aws/scope_shared/deploy/build_and_push_images.py --env "$ENV" --region "$REGION"

echo ""
echo "[2/3] Re-running ECS bootstrap (nonkube)..."
"$PYTHON" -c "
from tools.cloud_shared.env import load_dotenv
load_dotenv()
import os
os.environ.setdefault('CLOUD_REGION', '$REGION')
from tools.aws.scope_shared.deploy.deploy_common import run_ecs_bootstrap
run_ecs_bootstrap('$ENV', '$REGION')
"

echo ""
echo "[3/3] Re-running kube bootstrap (kube, --force)..."
"$PYTHON" tools/aws/kube/kube_apply.py --env "$ENV" --region "$REGION" --phase bootstrap --force

echo ""
echo "=== Done. Bootstrap tasks started. Wait 5-10 min, then verify: ==="
echo "  $PYTHON tools/aws/scope_shared/verify/verify_all_deploy.py --env $ENV --region $REGION --scope all"
echo ""
