/**
 * Data Management grid — Add Record dialog, pagination, row assert, delete.
 */
import { expect, type Locator, type Page } from "@playwright/test";
import type { SuperSaleRecord } from "../../support/scenarios";

export async function clickAddRecord(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Add Record" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "ID", exact: true })).toBeVisible();
  await expect(page.getByText("Add Record", { exact: true }).first()).toBeVisible();
}

async function fillDialogField(
  dialog: Locator,
  role: "textbox" | "spinbutton",
  name: string,
  value: string,
  exact = false,
): Promise<void> {
  const locator = dialog.getByRole(role, exact ? { name, exact: true } : { name });
  await locator.fill(value);
}

export async function fillRecordDialog(page: Page, record: SuperSaleRecord): Promise<void> {
  const dialog = page.getByRole("dialog");
  await fillDialogField(dialog, "textbox", "ID", record.id, true);
  await fillDialogField(dialog, "textbox", "Customer ID", record.customer_id);
  await fillDialogField(dialog, "textbox", "Brand", record.brand);
  await fillDialogField(dialog, "textbox", "Fridge Model", record.fridge_model);
  await fillDialogField(dialog, "spinbutton", "Price", String(record.price));
  await fillDialogField(dialog, "textbox", "Sales Date", record.sales_date);
  await fillDialogField(dialog, "textbox", "Store Name", record.store_name);
  await fillDialogField(dialog, "textbox", "Store Address", record.store_address);
  await fillDialogField(dialog, "textbox", "Customer Feedback", record.customer_feedback);
  await fillDialogField(dialog, "spinbutton", "Feedback Rating", String(record.feedback_rating));
  await fillDialogField(dialog, "textbox", "Sentiment Category", record.feedback_sentiment_category);
}

export async function saveRecordDialog(page: Page): Promise<void> {
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Save" }).click();
  const errorAlert = page.locator('.MuiAlert-standardError, [role="alert"]');
  try {
    await expect(dialog).toBeHidden({ timeout: 90_000 });
  } catch {
    if (await errorAlert.isVisible()) {
      const msg = await errorAlert.innerText();
      throw new Error(msg);
    }
    throw new Error("Save dialog did not close");
  }
}

export async function goToLastGridPage(page: Page): Promise<void> {
  const pagination = page.locator(".MuiTablePagination-root");
  await expect(pagination).toBeVisible({ timeout: 15_000 });
  const next = page.getByRole("button", { name: "Go to next page" });
  for (let i = 0; i < 50; i++) {
    if (!(await next.isEnabled())) {
      break;
    }
    await next.click();
    await page.waitForTimeout(300);
  }
}

function dataGridRow(page: Page, recordId: string) {
  return page.locator(`[role="row"][data-id="${recordId}"]`);
}

export async function assertRowOnPage(page: Page, record: SuperSaleRecord): Promise<void> {
  const row = dataGridRow(page, record.id);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await expect(row).toContainText(record.brand);
  await expect(row).toContainText(record.fridge_model);
  await expect(row).toContainText(Number(record.price).toLocaleString("en-US"));
  await expect(row).toContainText(record.store_name);
}

export async function scrollDataGridToActions(page: Page): Promise<void> {
  const scroller = page.locator(".MuiDataGrid-virtualScroller");
  await expect(scroller).toBeVisible({ timeout: 15_000 });
  await scroller.evaluate((el) => {
    el.scrollLeft = el.scrollWidth;
  });
}

export async function deleteRecordOnPage(page: Page, recordId: string): Promise<void> {
  const row = dataGridRow(page, recordId);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await scrollDataGridToActions(page);
  await row.getByRole("button", { name: "Delete" }).click({ force: true });
  await expect(page.getByRole("dialog")).toContainText(recordId);
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("dialog")).toBeHidden({ timeout: 30_000 });
}
