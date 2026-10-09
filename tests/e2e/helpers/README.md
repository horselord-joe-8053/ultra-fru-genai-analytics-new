# E2E helpers

Layer model (portuguese-learn pattern):

| Layer | Path | Imports |
|-------|------|---------|
| **L0 core** | `helpers/core/` | `@floor35/playwright-e2e`, `support/loadLocalPorts` |
| **L0 ui** | `helpers/ui/` | Playwright `Page` locators only |
| **L1 domain** | `domain/chat/`, `domain/crud/` | L0 + `support/scenarios` |

**Rule:** L0 must not import L1. Demos import L1 runners only.
