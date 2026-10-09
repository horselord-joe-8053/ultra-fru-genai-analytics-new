/**
 * Dump Istanbul ``window.__coverage__`` from an instrumented Vite bundle (Playwright E2E).
 *
 * Requires ``PW_COLLECT_COVERAGE=1`` and ``VITE_COVERAGE`` on the dev/preview server.
 */
import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

import { frontendCoverageDir, playwrightRawDir } from "./paths";

export function resolveFrontendCoverageDir(options?: { repoRoot?: string }): string {
  return frontendCoverageDir(options);
}

export function resolvePlaywrightRawDir(options?: { repoRoot?: string }): string {
  return playwrightRawDir(options);
}

export async function dumpPlaywrightCoverage(
  page: Page,
  outPath: string,
): Promise<boolean> {
  if (process.env.PW_COLLECT_COVERAGE !== "1") {
    return false;
  }
  const raw = await page.evaluate(() => {
    const g = globalThis as unknown as { __coverage__?: unknown };
    const w = window as unknown as { __coverage__?: unknown };
    const cov = g.__coverage__ ?? w.__coverage__;
    return cov === undefined ? null : JSON.stringify(cov);
  });
  if (!raw) {
    return false;
  }
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const slug = (process.env.RESALL_COV_PHASE_SLUG ?? "").trim();
  if (slug && outPath.includes(`e2e-${slug}.json`)) {
    let merged: Record<string, unknown> = {};
    if (fs.existsSync(outPath)) {
      try {
        merged = JSON.parse(fs.readFileSync(outPath, "utf8")) as Record<string, unknown>;
      } catch {
        merged = {};
      }
    }
    const chunk = JSON.parse(raw) as Record<string, unknown>;
    merged = { ...merged, ...chunk };
    fs.writeFileSync(outPath, JSON.stringify(merged), "utf8");
  } else {
    fs.writeFileSync(outPath, raw, "utf8");
  }
  return true;
}
