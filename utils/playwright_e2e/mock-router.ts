/**
 * Vite same-origin API proxy mock router — intercept JSON under configured path roots.
 */
import type { Page, Route } from "@playwright/test";

/** Default Floor35 Vite proxy roots (override per app). */
export const DEFAULT_VITE_PROXY_API_PATH_ROOTS = [
  "/auth",
  "/admin",
  "/practice",
  "/verbs",
  "/chapters",
  "/domains",
  "/conjugation",
] as const;

/** True when the request URL targets a proxied API path on the Vite origin. */
export function isProxiedApiUrl(
  url: string,
  roots: readonly string[] = DEFAULT_VITE_PROXY_API_PATH_ROOTS,
): boolean {
  let pathname: string;
  try {
    pathname = new URL(url).pathname;
  } catch {
    return false;
  }
  return roots.some((r) => pathname === r || pathname.startsWith(`${r}/`));
}

export type MockApiRouteHandler = (route: Route, url: string) => Promise<void>;

export type CreateProxyMockRouterOptions = {
  apiPathRoots?: readonly string[];
  /** When true, proxied API calls use ``route.continue()`` instead of the handler. */
  passThroughProxiedApi?: boolean;
  passthroughResourceTypes?: readonly string[];
};

/**
 * Intercept proxied API requests; pass through documents and non-API assets.
 * Handler receives only URLs where {@link isProxiedApiUrl} is true (unless pass-through).
 */
export async function createProxyMockRouter(
  page: Page,
  handler: MockApiRouteHandler,
  opts?: CreateProxyMockRouterOptions,
): Promise<void> {
  const roots = opts?.apiPathRoots ?? DEFAULT_VITE_PROXY_API_PATH_ROOTS;
  const passThrough = opts?.passThroughProxiedApi === true;
  const docTypes = opts?.passthroughResourceTypes ?? ["document"];

  await page.route("**/*", async (route) => {
    const req = route.request();
    if (docTypes.includes(req.resourceType())) {
      await route.continue();
      return;
    }
    const url = req.url();
    if (!isProxiedApiUrl(url, roots)) {
      await route.continue();
      return;
    }
    if (passThrough) {
      await route.continue();
      return;
    }
    await handler(route, url);
  });
}

/** Alias for {@link createProxyMockRouter} (legacy name in Floor35 E2E). */
export const routeMockApi = createProxyMockRouter;
