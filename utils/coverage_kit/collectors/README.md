# TypeScript collectors (`utils/coverage_kit/collectors/`)

Portable **frontend** coverage collectors (Vitest paths, Playwright Istanbul dumps). NPM package **`@floor35/coverage-collectors`**.

**Python reporters** live in the parent directory (`finalize.py`, `digesters/`, …). See **`../HOWTO_USE_COVERAGE_KIT.md`** — sections **1.1** (collectors install) and **5** (files to copy).

```json
{
  "dependencies": {
    "@floor35/coverage-collectors": "file:../../utils/coverage_kit/collectors"
  }
}
```

Keep **`DEFAULT_FRONTEND_COVERAGE_REL`** in sync with **`../cover_layout.py`**.
