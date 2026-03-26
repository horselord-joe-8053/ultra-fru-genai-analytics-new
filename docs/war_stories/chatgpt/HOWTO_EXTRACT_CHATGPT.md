# HOWTO: Extract conversation text from a shared ChatGPT link

> **Source:** War story **§1** in [WAR_STORIES_OTHER.md](../WAR_STORIES_OTHER.md).  
> **Goal:** Recover a readable transcript from `chatgpt.com/share/...` without scraping the HTML shell.

---

## 1. What we learned (end-to-end)

### 1.1 The UI link is not the data

A public share looks like:

`https://chatgpt.com/share/<share-id>`

Opening it shows the ChatGPT chrome (“Chat history”, login prompts). Fetching that URL with **`curl`** returns the **HTML shell**, not the conversation.

### 1.2 The real payload is a JSON API

The conversation lives at:

`https://chatgpt.com/backend-api/share/<share-id>`

The JSON has:

- **`title`**, **`conversation_id`**, timestamps
- **`mapping`** — graph of nodes (`parent` / `children` / `message`)
- **`linear_conversation`** — same thread in **UI order** (preferred for extraction)

Visible text is under `message.content`: usually **`content_type: "text"`** with **`parts`** (strings). User messages can be **`multimodal_text`**: **`parts`** mixes **strings** and **objects** (e.g. `image_asset_pointer`); filenames appear in **`message.metadata.attachments`**.

### 1.3 Why plain `curl` / Python `urllib` often failed

We saw **403** or **HTML** (Cloudflare / edge) for the same URL that **Chrome (even Incognito)** could load as JSON **without logging in** for many public shares. That is mostly **client fingerprinting** (TLS, HTTP/2, `Sec-Fetch-*`, real browser JS), not “secret Incognito cookies.”

Replaying **“Copy as cURL”** often returned **challenge HTML** (`/cdn-cgi/challenge-platform/`, `_cf_chl_opt`) because **`curl` does not run JavaScript**, cookies like `__cf_bm` are short-lived, and the TLS fingerprint still differs from Chrome.

### 1.4 What worked: headless Playwright (Chromium)

We put the **full working path** under **`docs/war_stories/chatgpt/playwright/`**:

| File | Role |
|------|------|
| **`fetch_share.mjs`** | Headless Chromium navigates to `backend-api/share/...` with browser-like headers, saves **`test_result/raw_json/result_YYMMDD_hhmmss.json`**, then calls the transcript step. |
| **`extract_transcript.mjs`** | Parses saved JSON: prefers **`linear_conversation`**, falls back to a DFS from **`client-created-root`** in **`mapping`**; skips hidden/system noise; handles multimodal **`parts`**; writes **`test_result/transcripts/result_YYMMDD_hhmmss.txt`**. |

No separate Python fetch script: the **curl/urllib approach was not reliable** for live fetch, so live retrieval is **Playwright-only** in this repo.

### 1.5 Manual fallback (browser already has JSON)

If you already have the JSON body (DevTools → Network → response for `backend-api/share/...`, or a HAR export):

1. Save it as a `.json` file.
2. Run **`node extract_transcript.mjs --json-file /path/to/saved.json -o transcript.txt`** from the **`playwright/`** directory (or pass absolute paths).

That path does **not** need Playwright—only **Node** to run the extractor.

---

## 2. Quick reference (minimal Python loop)

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

## 3. Install and run (new machine)

See **[playwright/README.md](./playwright/README.md)** for **Node**, **npm**, **Playwright / Chromium**, optional **Homebrew**, and Linux system libraries.

**Typical flow:**

```bash
cd docs/war_stories/chatgpt/playwright
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
cd docs/war_stories/chatgpt/playwright
node extract_transcript.mjs --json-file test_result/raw_json/result_YYMMDD_hhmmss.json \
  -o test_result/transcripts/result_YYMMDD_hhmmss.txt
```

**Exit codes (`fetch_share.mjs`):** **0** success; **2** Cloudflare/challenge HTML; **3** non-JSON body; **4** JSON parse error; **5** transcript step failed.

---

## 4. Caveats

- API shape and edge behavior can **change**; shares can **expire** or require stricter auth later.
- **`test_result/`** is **gitignored**; copy anything you want into versioned docs manually.

---

## Related

- [WAR_STORIES_OTHER.md §1](../WAR_STORIES_OTHER.md)
- [playwright/README.md](./playwright/README.md)
- [playwright/fetch_share.mjs](./playwright/fetch_share.mjs)
- [playwright/extract_transcript.mjs](./playwright/extract_transcript.mjs)
