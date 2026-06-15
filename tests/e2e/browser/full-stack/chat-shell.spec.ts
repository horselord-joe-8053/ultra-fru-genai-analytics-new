import { test, expect } from "@playwright/test";
import { skipUnlessStackHealthy } from "../../helpers/core/stack";
import { configStrip } from "../../helpers/ui/chat";
import { assertBatchPanelVisible } from "../../helpers/ui/batch-analytics";

test.describe("chat shell", () => {
  test.beforeEach(async ({ request }) => {
    await skipUnlessStackHealthy(request);
  });

  test("loads FRU Analytics Assistant with Build config strip", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "FRU Analytics Assistant" })).toBeVisible();
    await expect(configStrip(page)).toBeVisible({ timeout: 30_000 });
    await assertBatchPanelVisible(page);
  });
});
