/**
 * Demo Playwright config — one narrated tour test, slow-mo, trace + video on.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import baseConfig from "../../tests/e2e/playwright.config";

const demoRoot = path.dirname(fileURLToPath(import.meta.url));
const queryTimeout = Number.parseInt(process.env.E2E_QUERY_TIMEOUT_MS ?? "180000", 10);

export default defineConfig({
  ...baseConfig,
  testDir: path.join(demoRoot, "sequences"),
  outputDir: path.join(demoRoot, "test-results"),
  reporter: [["html", { outputFolder: path.join(demoRoot, "playwright-report") }]],
  use: {
    ...baseConfig.use,
    trace: "on",
    video: "on",
    launchOptions: {
      slowMo: Number.parseInt(process.env.PLAYWRIGHT_SLOW_MO_DELAY ?? "1000", 10) || 1000,
    },
  },
  workers: 1,
  projects: [
    {
      name: "demo",
      testDir: path.join(demoRoot, "sequences"),
      timeout: queryTimeout,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
