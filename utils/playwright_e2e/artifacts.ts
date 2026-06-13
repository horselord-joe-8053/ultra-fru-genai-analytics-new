/**
 * Playwright test attachments for structured debug payloads.
 */
import type { TestInfo } from "@playwright/test";

/** Attach JSON-serializable ``payload`` to the current test report. */
export async function attachJson(
  testInfo: TestInfo,
  name: string,
  payload: unknown,
): Promise<void> {
  await testInfo.attach(name, {
    body: JSON.stringify(payload, null, 2),
    contentType: "application/json",
  });
}
