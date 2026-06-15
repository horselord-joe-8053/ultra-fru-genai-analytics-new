#!/usr/bin/env bash
# Stack preflight + Playwright full-stack e2e (external orchestrator deploy).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/tests/e2e"

export PLAYWRIGHT_EXTERNAL_STACK="${PLAYWRIGHT_EXTERNAL_STACK:-1}"

API_PORT="${E2E_API_PORT:-5001}"
BASE="${INTEGRATION_API_BASE_URL:-http://localhost:${API_PORT}}"

if ! curl -sf "${BASE}/health" >/dev/null; then
  echo "Stack not up. Run: python orchestrator.py deploy --provider local --scope nonkube"
  exit 1
fi

if [[ ! -d node_modules ]]; then
  npm install
  npx playwright install chromium
fi

npm run test:e2e:full-stack "$@"
