# Live Playwright demos (`demos/playwright_e2e/`)

Stakeholder-facing, **slow-paced** narrated tour of analytics scenarios **S0–S5**. Not a CI gate — reuses helpers from `tests/e2e/` with **`strict: false`** (no keyword/grid asserts).

## Audience

Product demos, onboarding, regression walkthroughs with narration.

## Prerequisites

Same as [`tests/e2e/README.md`](../../tests/e2e/README.md):

```bash
python orchestrator.py deploy --provider local --scope nonkube
cd tests/e2e && npm install && npx playwright install chromium
```

## Run

```bash
./demos/playwright_e2e/scripts/run_demo.sh
```

Headed (visible browser) with slower pacing:

```bash
PLAYWRIGHT_EXTERNAL_STACK=1 PLAYWRIGHT_HEADLESS=0 PLAYWRIGHT_SLOW_MO_DELAY=1200 \
  ./demos/playwright_e2e/scripts/run_demo.sh
```

## Sequence (one Playwright test, nested `test.step` reports)

1. **S0** — config strip (Build, models, scope); batch panel visible
2. **S1–S4** — four chat turns on the **same** Main tab (one page load; chat history accumulates)
3. **S5** — Data Management super sale → chat best-city query → delete **F900** (no Batch Analytics ↻)
4. **Outro** — batch panel visible

Scenario strings live in `tests/e2e/support/scenarios.ts` only.

## vs e2e tests

| | Demo tour | `tests/e2e/` |
|---|-----------|--------------|
| Structure | One test, soft asserts | Six strict tests, isolated `goto` per chat scenario |
| S5 ↻ reload | Skipped | Skipped |
| CI gate | No | Yes (full-stack project) |

Artifacts: `demos/playwright_e2e/test-results/` (video/trace), `playwright-report/` (HTML).
