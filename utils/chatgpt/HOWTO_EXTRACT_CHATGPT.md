<h1 id="howto-extract-conversation-text-from-shared-chatgpt-link" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">HOWTO: Extract conversation text from a shared ChatGPT link</h1>

> **Goal:** Recover a readable transcript from `chatgpt.com/share/...` without scraping the HTML shell.  
> **Implementation:** **`playwright/`** (Node + Playwright Chromium). **Versioned example transcripts:** **`transcripts/`** (copy from `test_result/` after a successful fetch).

---

<h2 id="document-outline" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Document outline</h2>

1. [What we learned (end-to-end)](#1-what-we-learned-end-to-end) — API vs HTML, Playwright fix.
2. [Versioned transcripts (`transcripts/`)](#2-versioned-transcripts-transcripts) — naming, redacted tools.
3. [Quick reference (minimal Python loop)](#3-quick-reference-minimal-python-loop) — naive mapping snippet.
4. [Install and run (new machine)](#4-install-and-run-new-machine) — link to Playwright README.
5. [Caveats](#5-caveats) — API drift, gitignore.
6. [Related](#related) — sibling docs.

---

<h2 id="1-what-we-learned-end-to-end" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">1. What we learned (end-to-end)</h2>

<h3 id="11-the-ui-link-is-not-the-data" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.1 The UI link is not the data</h3>

A public share looks like:

`https://chatgpt.com/share/<share-id>`

Opening it shows the ChatGPT chrome (“Chat history”, login prompts). Fetching that URL with **`curl`** returns the **HTML shell**, not the conversation.

<h3 id="12-the-real-payload-is-a-json-api" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.2 The real payload is a JSON API</h3>

The conversation lives at:

`https://chatgpt.com/backend-api/share/<share-id>`

The JSON has:

- **`title`**, **`conversation_id`**, timestamps
- **`mapping`** — graph of nodes (`parent` / `children` / `message`)
- **`linear_conversation`** — same thread in **UI order** (preferred for extraction)

Visible text is under `message.content`: usually **`content_type: "text"`** with **`parts`** (strings). User messages can be **`multimodal_text`**: **`parts`** mixes **strings** and **objects** (e.g. `image_asset_pointer`); filenames appear in **`message.metadata.attachments`**.

<h3 id="13-why-plain-curl--python-urllib-often-failed" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.3 Why plain `curl` / Python `urllib` often failed</h3>

We saw **403** or **HTML** (Cloudflare / edge) for the same URL that **Chrome (even Incognito)** could load as JSON **without logging in** for many public shares. That is mostly **client fingerprinting** (TLS, HTTP/2, `Sec-Fetch-*`, real browser JS), not “secret Incognito cookies.”

Replaying **“Copy as cURL”** often returned **challenge HTML** (`/cdn-cgi/challenge-platform/`, `_cf_chl_opt`) because **`curl` does not run JavaScript**, cookies like `__cf_bm` are short-lived, and the TLS fingerprint still differs from Chrome.

<h3 id="14-what-worked-headless-playwright-chromium" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.4 What worked: headless Playwright (Chromium)</h3>

We put the **full working path** under **`utils/chatgpt/playwright/`** (this folder’s **`./playwright/`**):

| File | Role |
|------|------|
| **`fetch_share.mjs`** | Headless Chromium navigates to `backend-api/share/...` with browser-like headers, saves **`test_result/raw_json/result_YYMMDD_hhmmss.json`**, then calls the transcript step. |
| **`extract_transcript.mjs`** | Parses saved JSON: prefers **`linear_conversation`**, falls back to a DFS from **`client-created-root`** in **`mapping`**; skips hidden/system noise; handles multimodal **`parts`**; writes **`test_result/transcripts/result_YYMMDD_hhmmss.txt`**. |

No separate Python fetch script: the **curl/urllib approach was not reliable** for live fetch, so live retrieval is **Playwright-only** in this repo.

<h3 id="15-manual-fallback-browser-already-has-json" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.5 Manual fallback (browser already has JSON)</h3>

If you already have the JSON body (DevTools → Network → response for `backend-api/share/...`, or a HAR export):

1. Save it as a `.json` file.
2. Run **`node extract_transcript.mjs --json-file /path/to/saved.json -o transcript.txt`** from the **`playwright/`** directory (or pass absolute paths).

That path does **not** need Playwright—only **Node** to run the extractor.

---

<h2 id="2-versioned-transcripts-transcripts" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">2. Versioned transcripts (`transcripts/`)</h2>

After a successful `fetch_share.mjs` run, **copy** the generated `.txt` from `playwright/test_result/transcripts/` into **`utils/chatgpt/transcripts/`** so the conversation is tracked in git. Register it in [`transcripts/README.md`](./transcripts/README.md).

<h3 id="21-file-naming-human-readable-first" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">2.1 File naming (human-readable first)</h3>

Use a **short, meaningful slug** derived from the share **title** or topic, then the **share UUID**, so files sort by topic in file browsers:

- **Preferred:** `<slug>_<share-uuid>.txt`  
  Example: `cloud_certification_guidebooks_69de50eb-0cd4-839b-a5ea-86e45e2f06b3.txt`
- **Avoid** leading with the raw UUID only (harder to scan): ~~`69de50eb-0cd4-839b-a5ea-86e45e2f06b3_cloud_certification_guidebooks.txt`~~

Slug rules: lowercase, words separated by underscores, no spaces; keep it short but unambiguous.

<h3 id="22-redacted-tool-messages" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">2.2 Redacted tool messages</h3>

Public share JSON sometimes includes **`role=tool`** turns whose body is only:

```text
The output of this plugin was redacted.
```

That is **normal** for the export: you cannot recover the underlying plugin output (e.g. web search) from the share. **Leave those lines as-is** in the transcript. When citing them, point at the file and line range, for example:

`utils/chatgpt/transcripts/cloud_certification_guidebooks_69de50eb-0cd4-839b-a5ea-86e45e2f06b3.txt` (lines 5690–5691).

Assistant and user messages before and after are usually still complete.

---

<h2 id="3-quick-reference-minimal-python-loop" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">3. Quick reference (minimal Python loop)</h2>

If you are experimenting in a notebook and already have `data` loaded from JSON:

```python
mapping = data.get("mapping", {})
for node_id, node in mapping.items():
    if not isinstance(node, dict):
        continue
    msg = node.get("message")
    if not msg:
        continue
    author = msg.get("author", {}).get("role")
    content = msg.get("content", {})
    parts = content.get("parts") or []
    if not parts:
        continue
    # Naive: first string part only; real shares need multimodal + ordering (see extract_transcript.mjs)
    text = next((p for p in parts if isinstance(p, str) and p.strip()), None)
    if text:
        print(f"\n----- {author} -----\n{text}")
```

The **authoritative** extraction rules match **`playwright/extract_transcript.mjs`**.

---

<h2 id="4-install-and-run-new-machine" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">4. Install and run (new machine)</h2>

See **[playwright/README.md](./playwright/README.md)** for **Node**, **npm**, **Playwright / Chromium**, optional **Homebrew**, and Linux system libraries.

**Typical flow:**

```bash
cd utils/chatgpt/playwright
npm install
npx playwright install chromium
node fetch_share.mjs "https://chatgpt.com/share/<uuid>"
```

Or:

```bash
node fetch_share.mjs "https://chatgpt.com/backend-api/share/<uuid>"
```

**Outputs (gitignored under `test_result/`):**

- **`raw_json/result_YYMMDD_hhmmss.json`** — full API payload  
- **`transcripts/result_YYMMDD_hhmmss.txt`** — readable thread  

**`--out /path/to/file.json`** overrides **only** the JSON path; the transcript still goes to **`test_result/transcripts/<same-basename>.txt`**.

**Regenerate transcript from an existing JSON:**

```bash
cd utils/chatgpt/playwright
node extract_transcript.mjs --json-file test_result/raw_json/result_YYMMDD_hhmmss.json \
  -o test_result/transcripts/result_YYMMDD_hhmmss.txt
```

**Exit codes (`fetch_share.mjs`):** **0** success; **2** Cloudflare/challenge HTML; **3** non-JSON body; **4** JSON parse error; **5** transcript step failed.

---

<h2 id="5-caveats" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">5. Caveats</h2>

- API shape and edge behavior can **change**; shares can **expire** or require stricter auth later.
- **`test_result/`** is **gitignored**; copy anything you want into **`transcripts/`** (see `transcripts/README.md`) or into course notes.

---

<h2 id="related" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">6. Related</h2>

- [transcripts/README.md](./transcripts/README.md)
- [playwright/README.md](./playwright/README.md)
- [playwright/fetch_share.mjs](./playwright/fetch_share.mjs)
- [playwright/extract_transcript.mjs](./playwright/extract_transcript.mjs)
