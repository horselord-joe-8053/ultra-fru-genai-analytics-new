#!/usr/bin/env bash
# Preflight /health → one narrated tour (soft asserts). Uses tests/e2e node_modules via symlink.
# Headed: PLAYWRIGHT_HEADLESS=0 PLAYWRIGHT_SLOW_MO_DELAY=1200
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT/demos/playwright_e2e"

export PLAYWRIGHT_EXTERNAL_STACK="${PLAYWRIGHT_EXTERNAL_STACK:-1}"
export PLAYWRIGHT_SLOW_MO_DELAY="${PLAYWRIGHT_SLOW_MO_DELAY:-1000}"

API_PORT="${E2E_API_PORT:-5001}"
BASE="${INTEGRATION_API_BASE_URL:-http://localhost:${API_PORT}}"

echo "Checking ${BASE}/health ..."
if ! curl -sf "${BASE}/health" >/dev/null; then
  echo "Stack not up. Run: python orchestrator.py deploy --provider local --scope nonkube"
  exit 1
fi

cd "$REPO_ROOT/demos/playwright_e2e"
if [[ ! -e node_modules/@playwright/test ]]; then
  ln -sf ../../tests/e2e/node_modules node_modules
fi

PLAYWRIGHT_BIN="$REPO_ROOT/tests/e2e/node_modules/.bin/playwright"
if [[ ! -d "$REPO_ROOT/tests/e2e/node_modules" ]]; then
  cd "$REPO_ROOT/tests/e2e"
  npm install
  npx playwright install chromium
  cd "$REPO_ROOT/demos/playwright_e2e"
fi

"$PLAYWRIGHT_BIN" test --config playwright.demo.config.ts

echo "Demo complete. Report: demos/playwright_e2e/playwright-report/ (if generated)"
