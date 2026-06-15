/**
 * Execution log panel — wait for Completed or surface agent errors.
 */
import { expect, type Page } from "@playwright/test";

export async function waitForExecutionCompleted(page: Page, timeoutMs = 180_000): Promise<void> {
  const completed = page.getByText("● Completed");
  const errorLine = page.locator("text=Error:").first();
  await Promise.race([
    completed.waitFor({ state: "visible", timeout: timeoutMs }),
    errorLine.waitFor({ state: "visible", timeout: timeoutMs }).then(async () => {
      const msg = await errorLine.innerText();
      throw new Error(`Execution log error: ${msg}`);
    }),
  ]);
}

export async function assertNoExecutionError(page: Page): Promise<void> {
  const errorLine = page.locator('.text-red-600:has-text("Error:")');
  await expect(errorLine).toHaveCount(0);
}
