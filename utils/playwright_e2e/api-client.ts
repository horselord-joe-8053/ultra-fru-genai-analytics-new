/**
 * Thin JSON helpers over Playwright ``page.request`` (cookie jar follows the page).
 */
import type { APIRequestContext, APIResponse } from "@playwright/test";

export async function getJson<T = unknown>(
  request: APIRequestContext,
  url: string,
): Promise<{ response: APIResponse; body: T }> {
  const response = await request.get(url);
  const body = (await response.json()) as T;
  return { response, body };
}

export async function postJson<T = unknown>(
  request: APIRequestContext,
  url: string,
  data: unknown,
): Promise<{ response: APIResponse; body: T }> {
  const response = await request.post(url, { data });
  const body = (await response.json()) as T;
  return { response, body };
}

/** Poll ``predicate`` until it returns true or ``timeoutMs`` elapses. */
export async function pollUntil(
  predicate: () => Promise<boolean>,
  opts?: { intervalMs?: number; timeoutMs?: number },
): Promise<void> {
  const intervalMs = opts?.intervalMs ?? 250;
  const timeoutMs = opts?.timeoutMs ?? 30_000;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await predicate()) {
      return;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`pollUntil timed out after ${timeoutMs}ms`);
}
