/**
 * S5 super-sale CRUD journey — Data Management → chat → cleanup.
 * E2e: strict asserts, no Batch Analytics ↻. Demo tour: strict: false, same ↻ skip.
 */
import { test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import {
  E2E_SUPER_SALE_RECORD,
  S5_CRUD_JOURNEY,
  type SuperSaleRecord,
} from "../../support/scenarios";
import { apiBaseUrl } from "../../support/loadLocalPorts";
import { demoPause, logE2eStep } from "../../helpers/core/step-log";
import { goToDataManagementTab, goToMainTab } from "../../helpers/ui/tabs";
import {
  assertRowOnPage,
  clickAddRecord,
  deleteRecordOnPage,
  fillRecordDialog,
  goToLastGridPage,
  saveRecordDialog,
} from "../../helpers/ui/data-management";
import { runChatScenario } from "../chat/run-scenario";

export type SuperSaleJourneyOptions = {
  mode?: "test" | "demo";
  /** When false, skip grid row and chat keyword asserts. Default true. */
  strict?: boolean;
  /** Skip Batch Analytics ↻ reload (default true for test and demo). */
  skipBatchAnalyticsReload?: boolean;
  record?: SuperSaleRecord;
};

export async function deleteRecordViaApi(
  request: APIRequestContext,
  recordId: string,
): Promise<void> {
  const base = apiBaseUrl();
  try {
    await request.delete(`${base}/rawdata/${encodeURIComponent(recordId)}`, { timeout: 30_000 });
  } catch {
    // best-effort pre-cleanup
  }
}

export async function preflightDeleteF900(request: APIRequestContext): Promise<void> {
  await deleteRecordViaApi(request, E2E_SUPER_SALE_RECORD.id);
}

export async function runSuperSaleJourney(
  page: Page,
  options: SuperSaleJourneyOptions = {},
  testInfo?: TestInfo,
): Promise<void> {
  const mode = options.mode ?? "test";
  const strict = options.strict ?? true;
  const scope = mode === "demo" ? "demo" : "test";
  const record = options.record ?? E2E_SUPER_SALE_RECORD;

  logE2eStep(scope, "S5", "Data Management — Add Record", testInfo);
  await goToDataManagementTab(page);
  if (mode === "demo") await demoPause();

  await clickAddRecord(page);
  await fillRecordDialog(page, record);

  try {
    await saveRecordDialog(page);
  } catch (err) {
    const errText = String(err);
    if (
      errText.includes("OPENAI") ||
      errText.includes("embedding") ||
      errText.includes("embed")
    ) {
      test.skip(true, "OpenAI embedding not configured for CRUD POST");
    }
    throw err;
  }

  logE2eStep(scope, "S5", "Verify row on last page", testInfo);
  await goToLastGridPage(page);
  if (strict) {
    await assertRowOnPage(page, record);
  } else {
    logE2eStep(scope, "S5", `Row saved (soft): ${record.id}`, testInfo);
  }
  if (mode === "demo") await demoPause();

  logE2eStep(scope, "S5", `Main — ${S5_CRUD_JOURNEY.chatQuery}`, testInfo);
  await goToMainTab(page);
  if (mode === "demo") await demoPause();

  const s5Scenario = {
    id: "S5",
    query: S5_CRUD_JOURNEY.chatQuery,
    kind: "sql_geo_city" as const,
    expectedKeywords: S5_CRUD_JOURNEY.expectedAnswerKeywords,
  };
  await runChatScenario(page, s5Scenario, { mode, strict }, testInfo);

  logE2eStep(scope, "S5", "Delete F900", testInfo);
  await goToDataManagementTab(page);
  await goToLastGridPage(page);
  await deleteRecordOnPage(page, record.id);
}
