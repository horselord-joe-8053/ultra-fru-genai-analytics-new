<h1 id="howto-playwright-e2e" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">Using <code>@floor35/playwright-e2e</code></h1>

**Type:** how-to — **Audience:** repos that copy `utils/playwright_e2e/` (same pattern as `utils/neat_logger/`).

Portable Playwright primitives: external-stack guard, base URL helpers, descriptor login, Vite proxy mock router, JSON request helpers, test attachments. **No** imports from app `src/`.

---

<h2 id="outline">Document outline</h2>

1. [Files to copy](#files) — minimum bundle.
2. [Install in a consumer](#install) — `file:` dependency.
3. [Modules](#modules) — exports and when to use each.
4. [Floor35 wiring](#floor35) — how this repo extends the kit.

---

<h2 id="files">1. Files to copy</h2>

```text
utils/playwright_e2e/
  package.json
  index.ts
  stack.ts
  config.ts
  auth.ts
  mock-router.ts
  api-client.ts
  artifacts.ts
  HOWTO_USE_PLAYWRIGHT_E2E.md
```

Peer dependency: `@playwright/test` (match your Playwright major).

---

<h2 id="install">2. Install in a consumer</h2>

```json
{
  "dependencies": {
    "@floor35/playwright-e2e": "file:../../utils/playwright_e2e"
  }
}
```

```typescript
import { skipUnlessExternalPlaywrightStack } from "@floor35/playwright-e2e/stack";
import { createProxyMockRouter, isProxiedApiUrl } from "@floor35/playwright-e2e/mock-router";
import { signIn, type LoginPageDescriptor } from "@floor35/playwright-e2e/auth";
```

---

<h2 id="modules">3. Modules</h2>

| Module | Use when |
|--------|----------|
| `stack.ts` | Specs need a pre-started API + Vite (`PLAYWRIGHT_EXTERNAL_STACK=1`). |
| `config.ts` | Resolve preview base URL from `E2E_FRONTEND_PORT`. |
| `auth.ts` | App-agnostic login via `LoginPageDescriptor` (paths + locators). |
| `mock-router.ts` | Stub same-origin proxied API paths on the Vite dev server. |
| `api-client.ts` | `page.request` JSON GET/POST + `pollUntil`. |
| `artifacts.ts` | Attach JSON debug blobs to the HTML report. |

Override `DEFAULT_VITE_PROXY_API_PATH_ROOTS` when your Vite proxy table differs.

---

<h2 id="floor35">4. Floor35 wiring</h2>

| Concern | Location |
|---------|----------|
| App admin login | `tests/e2e/helpers/core/auth.ts` (`signInAsAdmin`) |
| Coverage pass-through mocks | `tests/e2e/helpers/mocked/route-api.ts` wraps `createProxyMockRouter` + `PW_PASS_API_TO_BACKEND` |
| PLGW / conjugation UI | `tests/e2e/domain/plgw/`, `tests/e2e/domain/conjugation/` |

See [`tests/e2e/README.md`](../../tests/e2e/README.md).
