/**
 * External-stack guard for Playwright projects that require a pre-started API + Vite.
 */
import { test } from "@playwright/test";

const DEFAULT_MESSAGE =
  "Set PLAYWRIGHT_EXTERNAL_STACK=1 and start the app stack (API + frontend) before running this project.";

/** Skip the current test unless ``PLAYWRIGHT_EXTERNAL_STACK=1``. */
export function skipUnlessExternalPlaywrightStack(message: string = DEFAULT_MESSAGE): void {
  test.skip(process.env.PLAYWRIGHT_EXTERNAL_STACK !== "1", message);
}
