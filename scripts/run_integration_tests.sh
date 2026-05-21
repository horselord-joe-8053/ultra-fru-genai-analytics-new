#!/usr/bin/env bash
# Run integration tests against a local API (Docker + orchestrator deploy).
# Prerequisite: python orchestrator.py deploy --provider local --scope all
set -euo pipefail
cd "$(dirname "$0")/.."
unset PYTEST_DISABLE_PLUGIN_AUTOLOAD 2>/dev/null || true
export INTEGRATION_API_BASE_URL="${INTEGRATION_API_BASE_URL:-http://localhost:${LOCAL_SERVER_PORT:-5001}}"
echo "Integration API base: $INTEGRATION_API_BASE_URL"
echo "Ensure stack is up: curl -s \"$INTEGRATION_API_BASE_URL/health\""
python -m pytest tests/integration -m integration -v "$@"
