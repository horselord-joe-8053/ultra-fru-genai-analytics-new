import { test } from "@playwright/test";
import { ANALYTICS_CHAT_SCENARIOS } from "../../support/scenarios";
import { skipUnlessStackHealthy } from "../../helpers/core/stack";
import { runChatScenario } from "../../domain/chat/run-scenario";

test.describe.configure({ mode: "serial" });

test.describe("analytics chat scenarios S1–S4", () => {
  test.beforeEach(async ({ request }) => {
    await skipUnlessStackHealthy(request);
  });

  for (const scenario of ANALYTICS_CHAT_SCENARIOS) {
    test(`${scenario.id}: ${scenario.query}`, async ({ page }, testInfo) => {
      await page.goto("/");
      await runChatScenario(page, scenario, { mode: "test" }, testInfo);
    });
  }
});
