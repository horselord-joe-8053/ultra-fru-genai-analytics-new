/**
 * Live demo tour — one Playwright test, narrated steps S0→outro.
 * S1–S4 share one page load (sequential chat). Soft asserts (`strict: false`); not a CI gate.
 */
import { test } from "@playwright/test";
import { ANALYTICS_CHAT_SCENARIOS } from "../../../tests/e2e/support/scenarios";
import { skipUnlessStackHealthy, skipUnlessExternalPlaywrightStack } from "../../../tests/e2e/helpers/core/stack";
import { runChatScenario } from "../../../tests/e2e/domain/chat/run-scenario";
import { runSuperSaleJourney } from "../../../tests/e2e/domain/crud/run-super-sale-journey";
import { configStrip } from "../../../tests/e2e/helpers/ui/chat";
import { assertBatchPanelVisible } from "../../../tests/e2e/helpers/ui/batch-analytics";
import { demoPause, logE2eStep } from "../../../tests/e2e/helpers/core/step-log";
import { preflightDeleteF900, deleteRecordViaApi } from "../../../tests/e2e/domain/crud/run-super-sale-journey";
import { E2E_SUPER_SALE_RECORD } from "../../../tests/e2e/support/scenarios";

test.describe.configure({ mode: "serial" });

test.describe("analytics assistant tour", () => {
  test.beforeEach(async ({ request }) => {
    skipUnlessExternalPlaywrightStack();
    await skipUnlessStackHealthy(request);
    await preflightDeleteF900(request);
  });

  test.afterEach(async ({ request }) => {
    await deleteRecordViaApi(request, E2E_SUPER_SALE_RECORD.id);
  });

  test("S0 through outro — narrated analytics tour", async ({ page }, testInfo) => {
    test.setTimeout(1_800_000);

    await test.step("S0 intro — config strip and batch panel", async () => {
      logE2eStep("demo", "S0", "Open UI — Build, models, scope", testInfo);
      await page.goto("/");
      await configStrip(page).waitFor({ state: "visible", timeout: 30_000 });
      await assertBatchPanelVisible(page);
      await demoPause(1500);
    });

    await test.step("S1–S4 chat — sequential turns on same page", async () => {
      for (const scenario of ANALYTICS_CHAT_SCENARIOS) {
        await runChatScenario(page, scenario, { mode: "demo", strict: false }, testInfo);
      }
    });

    await test.step("S5 CRUD journey — add, query, delete F900", async () => {
      await runSuperSaleJourney(
        page,
        { mode: "demo", strict: false, skipBatchAnalyticsReload: true },
        testInfo,
      );
    });

    await test.step("outro — batch panel visible", async () => {
      logE2eStep("demo", "outro", "Batch Analytics panel (no Spark trigger)", testInfo);
      await assertBatchPanelVisible(page);
      await demoPause();
    });
  });
});
