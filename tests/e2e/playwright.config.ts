/**
 * Playwright config for FRU Chat UI E2E (external stack: orchestrator Vite + API).
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import { frontendBaseUrl } from "./support/loadLocalPorts";

const e2eRoot = path.dirname(fileURLToPath(import.meta.url));
const externalStack = process.env.PLAYWRIGHT_EXTERNAL_STACK === "1";

function slowMoMs(): number | undefined {
  const raw = process.env.PLAYWRIGHT_SLOW_MO_DELAY?.trim();
  if (!raw) return undefined;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

const slowMo = slowMoMs();
const queryTimeout = Number.parseInt(process.env.E2E_QUERY_TIMEOUT_MS ?? "180000", 10);

export default defineConfig({
  outputDir: path.join(e2eRoot, "test-results"),
  timeout: 60_000,
  retries: Number.parseInt(process.env.PLAYWRIGHT_RETRIES ?? "0", 10) || 0,
  workers: 1,
  use: {
    baseURL: frontendBaseUrl(),
    trace: "on-first-retry",
    headless: process.env.PLAYWRIGHT_HEADLESS !== "0",
    ...(slowMo !== undefined ? { launchOptions: { slowMo } } : {}),
  },
  webServer: externalStack
    ? undefined
    : {
        command: "echo 'Set PLAYWRIGHT_EXTERNAL_STACK=1 and start orchestrator deploy'",
        port: 5174,
        reuseExistingServer: true,
      },
  projects: [
    {
      name: "full-stack",
      testDir: "./browser/full-stack",
      timeout: queryTimeout,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
