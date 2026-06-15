/**
 * Structured step logging for serial E2E journeys and demos.
 */
import type { TestInfo } from "@playwright/test";

export function logE2eStep(scope: string, stepId: string, message: string, testInfo?: TestInfo): void {
  const line = `[e2e][${scope}][${stepId}] ${message}`;
  console.log(line);
  testInfo?.annotations.push({ type: "step", description: `${stepId}: ${message}` });
}

export async function demoPause(ms?: number): Promise<void> {
  const raw = ms ?? Number.parseInt(process.env.PLAYWRIGHT_SLOW_MO_DELAY ?? "800", 10);
  const delay = Number.isFinite(raw) && raw > 0 ? raw : 800;
  await new Promise((r) => setTimeout(r, delay));
}
