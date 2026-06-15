<h1 id="chatgpt-share-playwright-fetch-transcript" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">ChatGPT share: Playwright fetch + transcript</h1>

All **working** code for this workflow lives in **`utils/chatgpt/playwright/`**.

- **`fetch_share.mjs`** — headless Chromium GET of `https://chatgpt.com/backend-api/share/<uuid>` (accepts pretty `/share/<uuid>` or backend URL).
- **`extract_transcript.mjs`** — turns saved share JSON into plain text (`linear_conversation` + multimodal `parts`).

Plain **`curl`** / Python **`urllib`** often get **403** or challenge **HTML** on the same URL; this stack uses a **real browser** via Playwright.

Parent HOWTO: [../HOWTO_EXTRACT_CHATGPT.md](../HOWTO_EXTRACT_CHATGPT.md)

<h2 id="document-outline" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Document outline</h2>

1. [Fresh machine setup](#fresh-machine-setup) — Node, npm, Chromium, optional Python note.
2. [One-liner (fetch + transcript)](#one-liner-fetch--transcript) — single command after setup.
3. [Outputs](#outputs) — JSON and transcript paths.
4. [Scripts (`package.json`)](#scripts-packagejson) — npm targets.
5. [More context](#more-context) — link to parent HOWTO.

---

<h2 id="fresh-machine-setup" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">1. Fresh machine setup</h2>

<h3 id="nodejs-required" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.1 Node.js (required)</h3>

- **macOS (Homebrew):** `brew install node`  
  Or install from [https://nodejs.org/](https://nodejs.org/) (LTS, **v18+** recommended).

- **Linux:** use your distro’s Node 18+ package or [NodeSource](https://github.com/nodesource/distributions) / nvm.

Check: `node -v` and `npm -v`.

<h3 id="install-npm-dependencies-and-chromium" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.2 Install npm dependencies and Chromium</h3>

From the **playwright** folder (`…/utils/chatgpt/playwright`):

```bash
cd utils/chatgpt/playwright
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

<h3 id="python-requirements-txt" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.3 Python / `requirements.txt`</h3>

This flow uses **Node only**. The repo’s **`requirements.txt`** is for the main Python app; it does **not** need extra packages for ChatGPT share extract. See the comment at the bottom of **`requirements.txt`**.

---

<h2 id="one-liner-fetch--transcript" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">2. One-liner (fetch + transcript)</h2>

After setup:

```bash
cd utils/chatgpt/playwright && npm ci && npx playwright install chromium && node fetch_share.mjs 'https://chatgpt.com/share/69c48336-b554-839c-8f93-1ec238001438'
```

---

<h2 id="outputs" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">3. Outputs</h2>

| Artifact | Path |
|----------|------|
| Raw API JSON | `test_result/raw_json/result_YYMMDD_hhmmss.json` |
| Transcript | `test_result/transcripts/result_YYMMDD_hhmmss.txt` |

`test_result/` is **gitignored**.

**Override JSON path:** `node fetch_share.mjs "<url>" --out /path/to/custom.json` — transcript still goes to **`test_result/transcripts/custom.txt`** (basename of the JSON file).

---

<h2 id="scripts-packagejson" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">4. Scripts (`package.json`)</h2>

| Command | Purpose |
|---------|---------|
| `npm test` | Sample fetch (public share URL in `package.json`). |
| `npm run fetch` | Run `fetch_share.mjs` (pass URL as extra args: `npm run fetch -- "https://..."`). |
| `npm run extract` | Run `extract_transcript.mjs` (pass args after `--`). |

**Extract only** (no browser):

```bash
cd utils/chatgpt/playwright
node extract_transcript.mjs --json-file test_result/raw_json/result_YYMMDD_hhmmss.json \
  -o test_result/transcripts/result_YYMMDD_hhmmss.txt
```

---

<h2 id="more-context" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">5. More context</h2>

[../HOWTO_EXTRACT_CHATGPT.md](../HOWTO_EXTRACT_CHATGPT.md) — problem, failed approaches, and the Playwright solution in one place.
