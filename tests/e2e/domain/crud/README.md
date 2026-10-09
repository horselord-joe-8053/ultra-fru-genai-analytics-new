# S5 CRUD journey

**Fixture:** `F900` / `CUST900` — SpaceX super sale at New York Store (`123 Broadway…` from seed F001).

## Steps (e2e — strict)

1. Data Management → Add Record → Save (UI jumps to last page)
2. Assert row on last grid page
3. Main → `Which city performed the best in revenue?` → expect **new york**
4. Delete **F900**

E2e sets `skipBatchAnalyticsReload: true` and `strict: true` (default). No Batch Analytics ↻ step.

## Demo tour (soft)

Same UI flow via `runSuperSaleJourney(page, { mode: "demo", strict: false, skipBatchAnalyticsReload: true })`:

- No keyword or grid content asserts
- No ↻ reload
- Invoked inside the single narrated tour in `demos/playwright_e2e/sequences/`

## Cleanup

- `preflightDeleteF900` in `beforeEach`
- `deleteRecordViaApi` in `afterEach` / `finally`
