/**
 * Stack guard and health preflight for FRU Playwright full-stack specs.
 */
import { test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import { apiBaseUrl } from "../../support/loadLocalPorts";

const DEFAULT_EXTERNAL_STACK_MSG =
  "Set PLAYWRIGHT_EXTERNAL_STACK=1 and start the app stack (API + Vite) before running this project.";

export function skipUnlessExternalPlaywrightStack(
  message: string = DEFAULT_EXTERNAL_STACK_MSG,
): void {
  test.skip(process.env.PLAYWRIGHT_EXTERNAL_STACK !== "1", message);
}

export async function skipUnlessStackHealthy(request: APIRequestContext): Promise<void> {
  skipUnlessExternalPlaywrightStack();
  const base = apiBaseUrl();
  try {
    const res = await request.get(`${base}/health`, { timeout: 10_000 });
    if (!res.ok()) {
      test.skip(true, `API /health not OK at ${base} (${res.status()})`);
    }
  } catch (err) {
    test.skip(
      true,
      `API unreachable at ${base}/health — run: python orchestrator.py deploy --provider local --scope nonkube`,
    );
  }
}

export async function isAgentLikelyDisabled(request: APIRequestContext): Promise<boolean> {
  const base = apiBaseUrl();
  const url = `${base}/query/stream?query=ping`;
  try {
    const res = await request.get(url, { timeout: 30_000 });
    const body = await res.text();
    return body.includes("Agent-based query processing is disabled");
  } catch {
    return false;
  }
}
