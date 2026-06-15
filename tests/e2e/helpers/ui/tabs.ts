/**
 * App tab switching (Main ↔ Data Management).
 */
import type { Page } from "@playwright/test";

export async function goToMainTab(page: Page): Promise<void> {
  await page.getByRole("tab", { name: "Main" }).click();
}

export async function goToDataManagementTab(page: Page): Promise<void> {
  await page.getByRole("tab", { name: "Data Management" }).click();
}
