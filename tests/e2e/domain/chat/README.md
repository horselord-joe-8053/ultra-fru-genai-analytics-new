# Chat scenario catalog (S1–S4)

Defined in [`support/scenarios.ts`](../../support/scenarios.ts). Used by `browser/full-stack/chat-scenarios.spec.ts` and `demos/playwright_e2e/`.

## Soft expectations

LLM phrasing varies — assertions use keyword lists or regex, not exact strings.

| ID | Pitfall |
|----|---------|
| S2 | State from `store_address` (3rd comma segment), not `store_name` |
| S3 | City from address; **Kansas City Store** ≠ city column |
| S4 | Semantic search — themes not exact feedback quotes |

## Flake sources

- Cold LLM start (raise `E2E_QUERY_TIMEOUT_MS`)
- Agent disabled (`USE_AGENT_QUERY=false`) — tests skip
- Missing API keys — skip via `/query/stream` probe
