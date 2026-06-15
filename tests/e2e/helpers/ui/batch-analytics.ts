/**
 * Batch Analytics panel — visibility and optional ↻ reload smoke.
 * Reload button a11y name: "Reload analytics snapshot" (visible glyph ↻).
 * Not used by demo tour or e2e S5 (both skip reload).
 */
import { expect, type Page } from "@playwright/test";

export function batchAnalyticsHeading(page: Page) {
  return page.getByRole("heading", { name: "Batch Analytics" });
}

/** Optional tour smoke — reload snapshot from server (does not run Spark). */
export async function clickBatchReload(page: Page): Promise<void> {
  const reloadBtn = page.getByRole("button", { name: "Reload analytics snapshot" });
  await expect(reloadBtn).toBeVisible();
  await reloadBtn.click();
  await expect(page.getByText("Reloading…")).toBeHidden({ timeout: 30_000 });
}

export async function assertBatchPanelVisible(page: Page): Promise<void> {
  await expect(batchAnalyticsHeading(page)).toBeVisible();
}
