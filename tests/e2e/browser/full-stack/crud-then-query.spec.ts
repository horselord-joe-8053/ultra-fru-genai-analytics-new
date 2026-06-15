import { test } from "@playwright/test";
import { E2E_SUPER_SALE_RECORD } from "../../support/scenarios";
import { skipUnlessStackHealthy } from "../../helpers/core/stack";
import {
  preflightDeleteF900,
  runSuperSaleJourney,
  deleteRecordViaApi,
} from "../../domain/crud/run-super-sale-journey";

test.describe.configure({ mode: "serial" });

test.describe("S5 CRUD then query", () => {
  test.beforeEach(async ({ request }) => {
    await skipUnlessStackHealthy(request);
    await preflightDeleteF900(request);
  });

  test.afterEach(async ({ request }) => {
    await deleteRecordViaApi(request, E2E_SUPER_SALE_RECORD.id);
  });

  test("add super sale, verify grid, ask best city, delete F900", async ({ page }, testInfo) => {
    test.setTimeout(360_000);
    await page.goto("/");
    await runSuperSaleJourney(page, { mode: "test", skipBatchAnalyticsReload: true }, testInfo);
  });
});
