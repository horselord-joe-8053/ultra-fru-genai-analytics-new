# ChatGPT share: Playwright fetch + transcript

All **working** code for this workflow lives in **`docs/war_stories/chatgpt/playwright/`**:

- **`fetch_share.mjs`** — headless Chromium GET of `https://chatgpt.com/backend-api/share/<uuid>` (accepts pretty `/share/<uuid>` or backend URL).
- **`extract_transcript.mjs`** — turns saved share JSON into plain text (`linear_conversation` + multimodal `parts`).

Plain **`curl`** / Python **`urllib`** often get **403** or challenge **HTML** on the same URL; this stack uses a **real browser** via Playwright.

---

## Fresh machine setup

### 1. Node.js (required)

- **macOS (Homebrew):** `brew install node`  
  Or install from [https://nodejs.org/](https://nodejs.org/) (LTS, **v18+** recommended).

- **Linux:** use your distro’s Node 18+ package or [NodeSource](https://github.com/nodesource/distributions) / nvm.

Check: `node -v` and `npm -v`.

### 2. Install npm dependencies and Chromium

From the **playwright** folder (repo root → `docs/war_stories/chatgpt/playwright`):

```bash
cd docs/war_stories/chatgpt/playwright
npm ci
```

Download the browser Playwright drives (one-time per machine, ~hundreds of MB):

```bash
npx playwright install chromium
```

**Linux only:** if Chromium fails to start, install OS libraries (Debian/Ubuntu example):

```bash
npx playwright install-deps chromium
```

On **macOS**, **Homebrew** is **not** required for Playwright itself once Node is installed; `playwright install chromium` pulls **Chrome for Testing** into Playwright’s cache.

### 3. Python / `requirements.txt`

This flow uses **Node only**. The repo’s **`requirements.txt`** is for the main Python app; it does **not** need extra packages for ChatGPT share extract. See the comment at the bottom of **`requirements.txt`**.

---

## One-liner (fetch + transcript)

After setup:

```bash
cd docs/war_stories/chatgpt/playwright && npm ci && npx playwright install chromium && node fetch_share.mjs 'https://chatgpt.com/share/69c48336-b554-839c-8f93-1ec238001438'
```

---

## Outputs

| Artifact | Path |
|----------|------|
| Raw API JSON | `test_result/raw_json/result_YYMMDD_hhmmss.json` |
| Transcript | `test_result/transcripts/result_YYMMDD_hhmmss.txt` |

`test_result/` is **gitignored**.

**Override JSON path:** `node fetch_share.mjs "<url>" --out /path/to/custom.json` — transcript still goes to **`test_result/transcripts/custom.txt`** (basename of the JSON file).

---

## Scripts (`package.json`)

| Command | Purpose |
|---------|---------|
| `npm test` | Sample fetch (public share URL in `package.json`). |
| `npm run fetch` | Run `fetch_share.mjs` (pass URL as extra args: `npm run fetch -- "https://..."`). |
| `npm run extract` | Run `extract_transcript.mjs` (pass args after `--`). |

**Extract only** (no browser):

```bash
cd docs/war_stories/chatgpt/playwright
node extract_transcript.mjs --json-file test_result/raw_json/result_YYMMDD_hhmmss.json \
  -o test_result/transcripts/result_YYMMDD_hhmmss.txt
```

---

## More context

[../HOWTO_EXTRACT_CHATGPT.md](../HOWTO_EXTRACT_CHATGPT.md) — problem, failed approaches, and the Playwright solution in one place.
