<h1 id="war-stories-other-title" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">WAR_STORIES_OTHER</h1>

A curated list of **non-trivial technical war stories**, capturing real lessons suitable for **senior-level interviews**.

**Authoring discipline:** `.cursor/rules/exwar-war-stories-extraction.mdc` and `.cursor/rules/mrkd-markdown-authoring.mdc`.

---

<h2 id="document-outline" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Document outline</h2>

1. [Reading guide](#reading-guide) — metadata and subsection labels.
2. [Story index](#story-index) — quick links to every story.

---

<h2 id="reading-guide" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Reading guide</h2>

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Field / label</th><th style="padding:8px">Meaning</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px"><strong>creation</strong> / <strong>last_updated</strong></td><td style="background:#e8f5e9;padding:8px">When the story was first captured and last revised (<code>&lt;YYMMDD&gt;</code> or <code>&lt;YYMMDD-HHMMSS&gt;</code>).</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>keywords</strong></td><td style="background:#e8f5e9;padding:8px">Grep-friendly index into problem area and stack.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>difficulty</strong> / <strong>significance</strong></td><td style="background:#e8f5e9;padding:8px">Relative depth (1–10) and how reusable the lesson is for interviews.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>N.1–N.5</strong></td><td style="background:#e8f5e9;padding:8px">Context → Root Cause → Key Insight → Resolution → Takeaway.</td></tr>
</tbody>
</table>

---

<h2 id="story-index" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Story index</h2>

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">#</th><th style="padding:8px">Title</th><th style="padding:8px">Gist</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">1</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-1">1. Scraping content from a shared ChatGPT link</a></td><td style="padding:8px;background:#fff3e0">Scraping content from a shared ChatGPT link</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">2</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-2">2. Docker Desktop disk image, external SSD, and “phantom” disk usage</a></td><td style="padding:8px;background:#e8f5e9">Docker Desktop disk image, external SSD, and “phantom” disk usage</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">3</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-3">3. Execution Log token usage — dual key shapes and backend run totals</a></td><td style="padding:8px;background:#fff3e0">SSE showed 0 tokens while section 4 was non-zero; normalize + accumulate on the server</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">4</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-4">4. City vs state in store_address — schema hints beat guessing SPLIT_PART indices</a></td><td style="padding:8px;background:#e8f5e9">LLM used index 2 for “state”; document 3-part address layout + few-shot city/state SQL</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">5</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-5">5. A capable Claude still needs semantic schema — thin column lists are not enough</a></td><td style="padding:8px;background:#fff3e0">generate_sql saw names/types only; world knowledge ≠ your table’s encoding</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">6</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-6">6. Docker Desktop Kubernetes can keep a stale API image in containerd</a></td><td style="padding:8px;background:#e8f5e9"><code>docker build</code> updates Docker Engine but kube node may not pick up the new digest until import</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">7</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-7-dual-embedding-sync">7. Dual-column storage vs single-column search</a></td><td style="padding:8px;background:#fff3e0">Populate all YAML profile columns on write; active profile is search-only</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">8</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-8-aws-rds-bootstrap">8. AWS bootstrap: RDS Data API dual-column sync without VPC job</a></td><td style="padding:8px;background:#e8f5e9">Shared embedding_sync_core + RDS adapter; bootstrap HTTPS vs ECS psycopg2 steady state</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">9</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-9-llm-inference-env">9. LLM_INFERENCE_PROVIDER: .env value ignored in Docker nonkube</a></td><td style="padding:8px;background:#fff3e0">Explicit chat provider enum + compose/kube/terraform must pass env into API process</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">10</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-10-spark-bootstrap-oom">10. Local Spark bootstrap exit 137 — shared Docker RAM and host schedulers</a></td><td style="padding:8px;background:#e8f5e9">OOM kill, not Spark logic; overlapping <code>docker run</code> + zombie JVMs on ~7.6 GiB host</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">11</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-11-analytics-worker-design">11. Compose analytics-worker — singleton owner for local nonkube Spark</a></td><td style="padding:8px;background:#fff3e0">Replace host <code>scheduler_local.py</code> + nested <code>docker run</code> with one Compose service + Forbid</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">12</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-12-local-vs-cloud-spark-scheduling">12. Why local uses a persistent worker but cloud keeps ephemeral tasks</a></td><td style="padding:8px;background:#e8f5e9">Shared laptop RAM vs isolated Fargate/Cloud Run memory — same job code, different wrappers</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">13</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-13-local-dual-ui-entry">13. Local nonkube — two UI entry points (Vite vs nginx bundle)</a></td><td style="padding:8px;background:#fff3e0">5001 serves UI+API by design; 5174 is dev Vite — not a routing bug</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">14</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-14-playwright-e2e-scenarios">14. Playwright E2E — shared scenarios, F900 CRUD, batch panel ≠ chat path</a></td><td style="padding:8px;background:#e8f5e9">One scenario module for tests+demos; S5 asserts chat/SQL not Spark snapshot</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">15</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-15-model-stack-catalog">15. Model stack catalog — embed filters chat, display parity</a></td><td style="padding:8px;background:#fff3e0">YAML stacks + server validation; log labels match dropdowns</td></tr>
</tbody>
</table>

---

<h2 id="war-story-1" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">1. Scraping content from a shared ChatGPT link</h2>

**creation:** `<260312>`

**last_updated:** `<260312>`

**keywords:** ChatGPT, shared links, JSON API, scraping, tooling

**difficulty:** 4  
**significance:** 6

---

<h3 id="war-story-1-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.1 Context</h3>

We had a public ChatGPT share URL like:

- `https://chatgpt.com/share/69afe889-6418-800c-9b1c-c80026928878`

Opening this in the browser showed only the generic ChatGPT UI (header, “Chat history”), and fetching it via `curl` or tooling returned just the **HTML shell**, without any of the conversation text we actually wanted to reuse for CI/CD and feature-flag documentation.

---

<h3 id="war-story-1-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.2 Root Cause</h3>

The share URL is **purely a UI endpoint**. The real conversation data lives behind a separate JSON endpoint:

- Extract the share ID:
  - `69afe889-6418-800c-9b1c-c80026928878`
- Use the backend endpoint instead:
  - `https://chatgpt.com/backend-api/share/69afe889-6418-800c-9b1c-c80026928878`

That endpoint returns a large JSON blob with a top-level `mapping` field. Each entry in `mapping` is a node in the conversation tree; some nodes contain a `message` with:

- `author.role` (`user`, `assistant`, or `system`)
- `content.parts` — a list of text chunks; the main text is in `parts[0]`

The HTML page we were hitting originally never exposed this JSON, so scraping it directly was a dead end.

---

<h3 id="war-story-1-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.3 Key Insight</h3>

> For ChatGPT share links, the **only reliable source of conversation text is the backend JSON (`/backend-api/share/<id>`)**, not the rendered HTML page.

Once we saw the JSON structure, the problem became a straightforward “walk a mapping and print `content.parts[0]`” task. The trick was:

- Follow the ID from the pretty URL.
- Switch to the backend API.
- Iterate `mapping` instead of trying to scrape the UI.

---

<h3 id="war-story-1-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.4 Resolution</h3>

Cursor saved the JSON to a local file under `agent-tools/`. We then used a small Python script to dump all messages.

From the project root:

```python
# One-off: python - << 'PY'  (from project root)
import json, os

path = os.path.join(
    os.path.expanduser("~"),
    ".cursor/projects/Users-jameswang9311-projects-fru-genai-analytics-new",
    "agent-tools",
    "9e406d97-133c-4de1-a5fb-da33314fd9d8.txt",
)

with open(path, "r") as f:
    data = json.load(f)

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
    text = parts[0]
    print(f"\n----- MESSAGE (role={author}) -----")
    print(text)
# PY
```

What this does:

- Loads the saved JSON.
- Iterates over all nodes in `mapping`.
- Filters to nodes with a `message` and non-empty `content.parts`.
- Prints each message, prefixed by its `role` so prompts and answers are easy to distinguish.

This was enough to recover the full CI/CD + feature-flag discussion that the HTML share page hid.

---

<h3 id="war-story-1-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.5 Takeaway</h3>

- **Don’t scrape the HTML shell** for ChatGPT shares; the real data is at `backend-api/share/<id>`.
- The JSON is **tree-structured**; for **correct order** and **multimodal** messages, use **`linear_conversation`** and the rules in **`utils/chatgpt/playwright/extract_transcript.mjs`** (a naive `mapping` loop is not enough).
- **Live fetch** from automation often hits **403** / Cloudflare; the repo’s working path is **Playwright** in **`utils/chatgpt/playwright/`** (see HOWTO).
- Once extracted, we could:
  - Rephrase and integrate the CI/CD + feature-flag insights into our own docs (`TODO_LEARNED_CICD.md`).
  - Keep our documentation **self-contained**, without relying on the external share remaining live.

This pattern is reusable any time we need to mine a shared ChatGPT conversation for architecture notes, war stories, or reference material.

**HOWTO + tooling:** [utils/chatgpt/HOWTO_EXTRACT_CHATGPT.md](../../utils/chatgpt/HOWTO_EXTRACT_CHATGPT.md) · [utils/chatgpt/playwright/](../../utils/chatgpt/playwright/) (`fetch_share.mjs`, `extract_transcript.mjs`)


---

<h2 id="war-story-2" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">2. Docker Desktop disk image, external SSD, and “phantom” disk usage</h2>

**creation:** `<260308>`  

**last_updated:** `<260308>`  

**keywords:** Docker Desktop, Docker.raw, sparse file, external SSD, APFS, macOS, disk space debugging  

**difficulty:** 6  
**significance:** 7

---

<h3 id="war-story-2-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.1 Context</h3>

We were running Docker Desktop with Kubernetes (kind) on a MacBook Air. Docker images and clusters were eating a lot of space, so we decided to move Docker Desktop’s disk image (`Docker.raw`) off the internal SSD onto an external SSD mounted at `/Volumes/Doc-Bk-JJ-SDD-1-APFS/`.

We:

- Changed **Settings → Resources → Advanced → Disk image location** to the external volume.  
- Manually copied `~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw` to the SSD.  
- Deleted the original `Docker.raw` on the internal disk expecting ~16–20 GB to be freed.

Instead, disk space behaved strangely:

- The free space barely moved at first.  
- Docker kept “recreating” a large `Docker.raw` on the internal disk.  
- At one point, there were **multiple `Docker.raw` files** on the SSD (`DockerDesktop/Docker.raw` and `DockerDesktop/DockerDesktop/Docker.raw`), and Docker’s VM was pointing at the nested one.

---

<h3 id="war-story-2-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.2 Root Causes</h3>

There were **three overlapping root causes**:

- **1) Sparse file vs. actual allocation**  
  - `du -sh Docker.raw` reported 16–228 GB, but APFS sparse files meant the *real* used blocks were much smaller (e.g. ~1 GB initially).  
  - Deleting a sparse file only freed the actually allocated blocks, not the apparent size, so the “freed GB” was less than it looked.

- **2) Open file handles preventing space from being released**  
  - We deleted `Docker.raw` while background `cp -Rp` processes were still copying it from the internal disk to the SSD.  
  - `lsof` showed `cp` still had `/Users/.../vms/0/data/Docker.raw` open. On Unix, deleting a file only unlinks the name; disk space is not reclaimed until all open handles close.  
  - Killing the `cp` processes (`kill -9 <pid>`) finally freed ~19 GB.

- **3) Misconfigured / reverted Docker disk image location**  
  - Docker sometimes started when the external SSD wasn’t mounted, or after an upgrade, and silently fell back to the default `~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw`.  
  - At another point, we accidentally pointed Docker at `/Volumes/.../DockerDesktop_raw/DockerDesktop`, and a script created a nested path `DockerDesktop/DockerDesktop/Docker.raw`.  
  - As a result, Docker kept **recreating a new local `Docker.raw`** on the internal disk, slowly eroding space again.

---

<h3 id="war-story-2-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.3 Resolution</h3>

We stabilized the setup with a combination of **process, path, and tooling fixes**:

- **Freeing the “stuck” space**
  - Used `lsof +L1` and `lsof | grep 'Docker.raw'` to find processes that still had deleted `Docker.raw` open.  
  - Killed the offending `cp` processes so the kernel could finally release the underlying blocks.  
  - Confirmed via `df -h /` that free space jumped from ~355 MB to ~19 GB.

- **Correctly relocating Docker to the SSD**
  - Ensured the external SSD was mounted **before starting Docker**.  
  - In Docker Desktop settings, set *Disk image location* to `/Volumes/Doc-Bk-JJ-SDD-1-APFS/DockerDesktop_raw`.  
  - Quit Docker, removed any stray `Docker.raw` on the internal disk, and let Docker create a new image on the SSD only.

- **Recovering from a likely-corrupted SSD `Docker.raw`**
  - Noticed that the nested path `.../DockerDesktop/DockerDesktop/Docker.raw` was smaller and had been mid-copy when `cp` was killed → likely corrupted.  
  - Chose **Option B**: delete that nested file and let Docker create a fresh empty disk on the SSD, at the cost of repulling images.

---

<h3 id="war-story-2-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.4 Takeaways</h3>

- **Deleting a big file ≠ instant space back** if any process still has it open; use `lsof +L1` before assuming the disk is “lying”.  
- **Sparse files** (like `Docker.raw`) can be hundreds of GB logically but only a few GB physically; always trust `du` and `df`, not just `ls -lh`.  
- When relocating Docker Desktop:
  - Make sure the external volume is mounted *before* Docker starts.  
  - After upgrades or reboots, re-check the disk image location; Docker may revert to the default silently.  
  - Avoid copying `Docker.raw` while Docker is running; treat it like a VM disk, not a regular file.
- In stubborn “Docker is wedged” situations, keep a script like `docker-unstick-desktop-start.sh` and clear, repeatable steps for:
  - Quitting Docker,  
  - Killing backend processes,  
  - Verifying no one is holding `Docker.raw`,  
  - Then safely deleting or relocating the disk image.

---

<h2 id="war-story-3" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">3. Execution Log token usage — dual key shapes and backend run totals</h2>

**creation:** `<260521>`

**last_updated:** `<260521>`

**keywords:** SSE, execution log, token usage, design, agent, pseudo_tool, normalize, backend-authoritative

**difficulty:** 5  
**significance:** 7

---

<h3 id="war-story-3-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.1 Context</h3>

The Execution Log panel streams agent steps over SSE (`tool_call_complete` per tool, `complete` at the end). Users expected **per-step** LLM token lines and a **section 4 total** that matched the sum of every LLM call (planning, `generate_sql`, synthesis). Instead, synthesis rows showed `0, 0, 0` while section 4 sometimes showed non-zero totals — and planning tokens never appeared at all.

---

<h3 id="war-story-3-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.2 Root Cause</h3>

Three separate issues compounded:

| Layer | Bug |
|-------|-----|
| **Claude client** | Returns `{input, output, total}` on each `claude_complete` call. |
| **Synthesis SSE** | Passed that raw dict through; the UI read `input_tokens` / `output_tokens` / `total_tokens` → all **zero**. |
| **Section 4** | `complete.token_usage` was built from **synthesis only**, not planning or `generate_sql`. |
| **Planning** | Tokens logged at DEBUG; no `tool_call_complete` row, so the panel had nothing to render. |

A frontend-only fix (mapping keys in React) would still leave section 4 wrong and would not survive stream disconnects. Client-side summation would diverge from the API’s non-stream `POST /query` response.

---

<h3 id="war-story-3-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.3 Key Insight</h3>

Treat the Execution Log as a **display contract** owned by the backend:

1. **One canonical shape** — `normalize_token_usage()` maps both Claude and normalized keys to `{input_tokens, output_tokens, total_tokens}` before any SSE payload or logger call.
2. **One accumulator** — `run_token_usage` in `process_query` adds every LLM step; `complete` and `POST /query` both return that sum.
3. **Pseudo-tools for invisible LLM work** — `pseudo_tool#llm_plan` streams planning like synthesis (`pseudo_tool#llm_synthesize_answer`) without registering a real agent tool.

Non-LLM steps (`execute_sql`) omit usage or show `(no token info from the LLM)` in the UI.

---

<h3 id="war-story-3-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.4 Resolution</h3>

- Added `normalize_token_usage` / `add_token_usage` in `display_truncate.py`.
- After each planning `claude_complete`, emit `tool_call_complete` with `tool: pseudo_tool#llm_plan`.
- `SQLGeneratorTool` returns `tokens` in tool output; SSE builder attaches normalized `output.token_usage` (agent `tool_results` summaries unchanged).
- Synthesis and `logger.log_synthesis` receive normalized usage → server log `Tokens:` matches the UI.
- Integration tests in `tests/integration/test_exec_log_sse.py` assert quoted SQL, normalized keys on LLM rows, and `complete.total_tokens == sum(step totals)`.

---

<h3 id="war-story-3-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.5 Takeaway</h3>

When the same metric crosses **multiple event types** (per-step SSE + final summary + REST JSON), pick a **single server-side normalizer and accumulator** early. Dual key shapes from upstream SDKs are common; fixing them in the UI alone hides half the bug and breaks DRY between stream and non-stream paths.

---

<h2 id="war-story-4" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">4. City vs state in store_address — schema hints beat guessing SPLIT_PART indices</h2>

**creation:** 260521-143000

**last_updated:** 260521-143000

**keywords:** design, data model design, text-to-sql, PostgreSQL, SPLIT_PART, store_address, schema hints, LLM agent, geography, few-shot prompts

**difficulty:** 5

**significance:** 7

---

<h3 id="war-story-4-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.1 Context</h3>

FRU sales rows store location in a single `store_address` TEXT column (US mailing layout) plus a separate `store_name` display label. After the PostgreSQL dialect migration (`SUBSTRING_INDEX` → `SPLIT_PART`), geography questions still failed in production:

- **“Which US state has the highest total sales revenue?”** → SQL grouped by `SPLIT_PART(store_address, ',', 2)` and the answer named **Kansas City** (a city, not a state abbreviation).
- **“Which city performed the best?”** → sometimes confused with `store_name` (e.g. `"Kansas City Store"`) instead of parsing the address.

The Execution Log showed **valid PostgreSQL** that executed cleanly — wrong semantics, not a syntax error.

---

<h3 id="war-story-4-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.2 Root Cause</h3>

Three traps stacked:

| Trap | What happened |
| --- | --- |
| **Opaque composite column** | Schema listed `store_address: TEXT` with no decomposition contract. The model had to invent which comma-separated segment meant “city” vs “state”. |
| **Off-by-one intuition on indices** | For `"123 Broadway, New York, NY 10001"`, index **2** is the **city** (`New York`). State abbreviation lives in part **3** as the first token before the zip (`NY`). The model reused index 2 for “state” because it is the second human-visible segment after the street. |
| **Misleading display field** | `store_name` values like `"Kansas City Store"` look geographic but are marketing labels — not a normalized city or state column. |

Sample row from `core_app/data/raw/fridge_sales_with_rating.csv`:

```text
STORE_NAME=Chicago Store
STORE_ADDRESS="456 Michigan Ave, Chicago, IL 60601"
```

Without an explicit layout, the LLM treats `store_address` like a bag of tokens and picks the most convenient `SPLIT_PART` index for the question wording.

---

<h3 id="war-story-4-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.3 Key Insight</h3>

<span style="background:#fff3e0;padding:2px 6px">For text-to-SQL over composite TEXT fields, document the **physical layout** in the schema prompt — indices, delimiters, and anti-patterns — not just the column type.</span>

A column name like `store_address` suggests meaning to humans but not to the model. The fix is a **decomposition contract**: fixed 3-part format, which index is city, how to extract state from part 3, and explicit guidance to prefer parsed address over `store_name` for geography.

---

<h3 id="war-story-4-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.4 Resolution</h3>

Documented the layout in **three places** so planner, SQL generator, and synthesis stay aligned:

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Layer</th><th style="padding:8px">What we added</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px"><code>sql_generator_tool._format_schema_info()</code></td><td style="background:#e8f5e9;padding:8px">3-part US format <code>"&lt;street&gt;, &lt;city&gt;, &lt;ST&gt; &lt;zip&gt;"</code>; index 2 = city; index 3 first token = state abbr; <code>store_name</code> is display-only.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><code>sql_generator_tool</code> rules + few-shot</td><td style="background:#e8f5e9;padding:8px">Separate city and state examples; rule <strong>“Index 2 is city, NOT state”</strong>; state uses nested <code>TRIM(SPLIT_PART(TRIM(SPLIT_PART(..., 3)), ' ', 1))</code>.</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><code>prompts.get_agent_system_prompt</code></td><td style="background:#e8f5e9;padding:8px">Same <code>store_address</code> hints for the query agent (planner / synthesis), not only the SQL tool.</td></tr>
</tbody>
</table>

**Address decomposition (canonical):**

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'9px'}}}%%
flowchart LR
  A["store_address TEXT"] --> P1["Part 1: street"]
  A --> P2["Part 2: city<br/>SPLIT_PART(..., ',', 2)"]
  A --> P3["Part 3: ST + zip<br/>first token = state abbr"]
  SN["store_name label<br/>(e.g. Kansas City Store)"] -.->|display only| A
  style P2 fill:#e8f5e9,stroke:#2e7d32,stroke-width:1px
  style P3 fill:#e3f2fd,stroke:#1565c0,stroke-width:1px
  style SN fill:#fff3e0,stroke:#ef6c00,stroke-width:1px
```

**Representative SQL (state vs city):**

```sql
-- City (index 2)
SELECT TRIM(SPLIT_PART(store_address, ',', 2)) AS city, SUM(price) AS total_sales
FROM fru_sales_embeddings
GROUP BY TRIM(SPLIT_PART(store_address, ',', 2));

-- State abbreviation (first token of part 3 — NOT index 2)
SELECT TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1)) AS state_abbr,
       SUM(price) AS total_sales
FROM fru_sales_embeddings
GROUP BY TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1));
```

**Verification:**

- Unit: `tests/unit/core_app/backend/test_sql_generator_postgresql.py` — `test_schema_prompt_documents_store_address_city_and_state` asserts format docs and **“Index 2 is city, NOT state”** in the generator prompt.
- Live: “which state performed the best” → **CA**; “which city performed the best” → **Houston** / **Kansas City** per parsed city column (not conflated with state).

---

<h3 id="war-story-4-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.5 Takeaway</h3>

When analytics data packs multiple facts into one TEXT column, **teach the decomposition in the prompt** (layout table, worked examples, and explicit “do not use index N for X”). Dialect rewrites fix *how* SQL runs; they do not fix *what* each comma-separated part means — that contract belongs in schema hints shared across every agent surface that touches geography.

---

<h2 id="war-story-5" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">5. A capable Claude still needs semantic schema — thin column lists are not enough</h2>

**creation:** 260521-150000

**last_updated:** 260521-150000

**keywords:** design, system design, text-to-sql, Claude, schema hints, few-shot prompts, LLM agent, prompt engineering, generate_sql, under-specified context

**difficulty:** 4

**significance:** 8

---

<h3 id="war-story-5-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.1 Context</h3>

After a bad “best performing **state**” answer returned **Kansas City**, the natural reaction was: *“A smart model should know how to find state in an address — we sent this to Claude, right?”*

Yes — but not in the way people imagine. The query agent **does** call Claude. Geography SQL is produced by a **second**, dedicated `claude_complete` inside `SQLGeneratorTool.generate_sql`, with its **own** system prompt built from `schema_info` and few-shot examples. The planner never pastes sample rows into that call.

Before the schema-hint fix ([story 4](#war-story-4)), that prompt was essentially:

```text
Table: fru_sales_embeddings
  - store_name: TEXT
  - store_address: TEXT
  - price: NUMERIC
  …
```

No sample values. No `"street, city, ST zip"` layout. No worked “extract state abbreviation” example. The model had column **names** and **types** — not the **encoding** your team chose for this dataset.

---

<h3 id="war-story-5-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.2 Root Cause</h3>

<span style="background:#fff3e0;padding:2px 6px">Model capability and model **context** are different problems.</span> Claude can reason about US addresses in the abstract. It cannot reliably infer **your** comma indices, **your** decision to pack city+state+zip into one TEXT column, or **your** few-shot habits — unless you put that in the prompt.

What the SQL generator actually had to work with:

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Prompt ingredient</th><th style="padding:8px">Before fix</th><th style="padding:8px">Effect on “best state” query</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px">Schema block</td><td style="background:#ffebee;padding:8px"><code>store_address: TEXT</code> only</td><td style="background:#ffebee;padding:8px">Model invents parsing; aliases index 2 as <code>state</code></td></tr>
<tr><td style="background:#e3f2fd;padding:8px">Sample rows</td><td style="background:#ffebee;padding:8px">None in generator prompt</td><td style="background:#ffebee;padding:8px">No anchor for <code>852 Main St, Kansas City, MO 64105</code> shape</td></tr>
<tr><td style="background:#e3f2fd;padding:8px">Few-shot: city</td><td style="background:#fff3e0;padding:8px">Often <code>store_name</code></td><td style="background:#fff3e0;padding:8px">Teaches display label, not parsed city</td></tr>
<tr><td style="background:#e3f2fd;padding:8px">Few-shot: region</td><td style="background:#fff3e0;padding:8px">Big <code>CASE</code> + <code>LIKE</code> on full address</td><td style="background:#fff3e0;padding:8px">Different pattern than state-abbr extraction</td></tr>
<tr><td style="background:#e3f2fd;padding:8px">Few-shot: state</td><td style="background:#ffebee;padding:8px">Missing</td><td style="background:#ffebee;padding:8px">No demonstrated <code>SPLIT_PART</code> recipe for ST</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><code>execute_sql</code></td><td style="background:#ffebee;padding:8px">Runs any valid SELECT</td><td style="background:#ffebee;padding:8px">Wrong semantics execute cleanly; Kansas City “wins”</td></tr>
</tbody>
</table>

The failure looked like “the model doesn’t understand addresses.” Mechanically it was **under-specified text-to-SQL**: plausible SQL, wrong column semantics. Synthesis sometimes **noticed** the mistake (“Kansas City … appears to be a city rather than a state”) — but only **after** bad SQL had already run and shaped the answer.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'9px'}}}%%
flowchart TB
  Q["User: best performing state?"] --> P["Planner Claude<br/>chooses generate_sql"]
  P --> G["generate_sql Claude<br/>thin schema + few-shots"]
  G --> SQL["SPLIT_PART(..., 2) AS state"]
  SQL --> X["execute_sql<br/>no address semantics check"]
  X --> R["Result: Kansas City"]
  R --> S["Synthesis Claude<br/>may spot error too late"]
  style G fill:#fff3e0,stroke:#ef6c00,stroke-width:1px
  style X fill:#ffebee,stroke:#c62828,stroke-width:1px
```

---

<h3 id="war-story-5-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.3 Key Insight</h3>

<span style="background:#e8f5e9;padding:2px 6px">Upgrading the model does not replace **semantic schema documentation**.</span>

For agentic analytics, treat the SQL generator prompt like an **API contract**:

1. **Physical layout** for composite fields (format string, indices, anti-patterns).
2. **Worked examples** per question family (city vs state vs region — not interchangeable).
3. **Consistency** across surfaces (`sql_generator_tool`, `prompts.py` agent schema, tests that assert hints exist).

World knowledge fills gaps when data is conventional. Enterprise tables are often **conventional-looking but idiosyncratic** — one TEXT column, marketing `store_name`, comma rules that differ from “obvious” US parsing. The model must be told **your** rules, not assumed to discover them.

---

<h3 id="war-story-5-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.4 Resolution</h3>

Enriched the generator and agent prompts (see [story 4](#war-story-4) for the address layout detail):

| Enhancement | Where | Why it matters |
| --- | --- | --- |
| **Semantic `store_address` block** | `_format_schema_info()`, `prompts.py` | Explains 3-part layout; city = index 2; state abbr = first token of part 3; <code>store_name</code> is display-only |
| **Explicit anti-pattern** | SQL generator rules | **“Index 2 is city, NOT state”** — blocks the exact failure mode |
| **Paired few-shots** | `sql_generator_tool.py` | Separate “highest city” and “highest state” examples with correct expressions |
| **Regression guard** | `test_schema_prompt_documents_store_address_city_and_state` | Prompt drift is caught in CI — thin schema cannot silently return |

**Thin vs enriched schema (what Claude sees):**

```text
# Thin (insufficient)
store_address: TEXT

# Enriched (what we ship now)
store_address format: "<street>, <city>, <ST> <zip>"
  Part 2 (index 2): city — TRIM(SPLIT_PART(store_address, ',', 2))
  Part 3: state abbr — TRIM(SPLIT_PART(TRIM(SPLIT_PART(store_address, ',', 3)), ' ', 1))
  store_name: display label only; prefer parsed address for geography
```

Longer-term alternative (not required for the lesson): normalized `city` / `state_abbr` columns or a DB view so the model never parses strings. Until then, **prompt-level semantic schema is mandatory**, not a nice-to-have.

**Verification:** Live queries — “which state performed the best” → **CA**; unit test locks prompt content.

---

<h3 id="war-story-5-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.5 Takeaway</h3>

If you pay for a frontier model and still get confidently wrong analytics, check **what you told it about your tables** before blaming model IQ. Text-to-SQL at production quality needs **semantic schema enrichment** — layout, examples, and tests — on top of raw column lists. Smarter models reduce variance; they do not absolve you of encoding **your** data model in the prompt.

---

<h2 id="war-story-6" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">6. Docker Desktop Kubernetes can keep a stale API image in containerd</h2>

**creation:** 260521 · **last_updated:** 260521 · **keywords:** docker desktop, kubernetes, containerd, local deploy, stale image, fru-api · **difficulty:** 6 · **significance:** 8

<h3 id="war-story-6-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.1 Context</h3>

Local **kube** scope builds `fru-api:local` with `docker build`, applies manifests, and rolls out `deployment/fru-api`. After embedding-profile and SQL-agent changes, the API on NodePort `30080` still behaved like an **older** build: missing schema hints, wrong SQL dialect helpers, and no profile-aware semantic search — even though `docker images` showed a fresh `fru-api:local` on the host.

<h3 id="war-story-6-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.2 Root Cause</h3>

Docker Desktop’s embedded Kubernetes node (`desktop-control-plane`) runs **containerd**, not the Docker Engine graph the CLI updates. `kubectl rollout restart` re-pulls the image **from the node’s image store**. If that store still holds an older digest tagged `fru-api:local`, pods come back with stale code while `docker build` on the host succeeded.

<h3 id="war-story-6-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.3 Key Insight</h3>

“Image rebuilt” ≠ “kube workload updated” on Docker Desktop. Treat **import into the k8s node** as part of the local kube deploy loop whenever API behavior does not match the latest build.

<h3 id="war-story-6-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.4 Resolution</h3>

After `docker build -t fru-api:local`, pipe the tarball into the control-plane containerd namespace:

```bash
docker save fru-api:local | docker exec -i desktop-control-plane ctr -n k8s.io images import -
kubectl rollout restart deployment/fru-api -n fru-kube
```

Automated in `tools/local/deploy.py` (`_import_api_image_to_kube_node()`). Documented in `docs/BYTEPLUS_AWS_GCP_REFERENCE.md` and the ModelArk refactor plan.

<h3 id="war-story-6-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.5 Takeaway</h3>

For local k8s on Docker Desktop, add an explicit **host → node image sync** step to your deploy checklist. Symptom: code changes “do nothing” after rollout; fix: verify pod image digest or import before blaming application logic.

---

<h2 id="war-story-7-dual-embedding-sync" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">7. Dual-column storage vs single-column search; Skylark multimodal API</h2>

**creation:** 260621 · **last_updated:** 260621 · **keywords:** embedding profiles, pgvector, ModelArk, multimodal, CRUD, embedding_sync · **difficulty:** 7 · **significance:** 8

<h3 id="war-story-7-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.1 Context</h3>

Embedding profiles introduced `embedding_openai_1536` and `embedding_skylark_2048`, with `EMBEDDING_ACTIVE_PROFILE` selecting the ANN search column. Initial ingest and CRUD only embedded the **active** column; CSV backfill missed API-added rows (201 DB rows vs 200 CSV). Skylark backfill against `/embeddings` returned HTTP 500.

<h3 id="war-story-7-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.2 Root Cause</h3>

Two separate issues: (1) **write path** tied to active profile and CSV source of truth; (2) `skylark-embedding-vision-*` requires **`/embeddings/multimodal`** with `{type:text}` input, not OpenAI-style batch `/embeddings`.

<h3 id="war-story-7-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.3 Key Insight</h3>

Split **storage** (populate all YAML profile columns via `embedding_sync` from DB) from **search** (`EMBEDDING_ACTIVE_PROFILE` read-only). Never gate CRUD or bootstrap embeds on the active env var.

<h3 id="war-story-7-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.4 Resolution</h3>

`backend.services.embedding_sync` syncs all credentialed profiles per row; scalar CSV load decoupled; `ModelArkEmbeddingClient` uses multimodal endpoint for vision models.

<h3 id="war-story-7-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.5 Takeaway</h3>

When adding a second embedding column, assume UI CRUD and non-CSV rows exist — backfill from **Postgres**, not the seed file. For BytePlus vision embed models, read the multimodal API doc before assuming OpenAI-compatible `/embeddings`.

<h2 id="war-story-8-aws-rds-bootstrap" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">8. AWS bootstrap: RDS Data API dual-column sync without VPC job</h2>

**creation:** 260621 · **last_updated:** 260621 · **keywords:** AWS, RDS Data API, Aurora, embedding_sync_rds, bootstrap, psycopg2, ECS · **difficulty:** 7 · **significance:** 8

<h3 id="war-story-8-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.1 Context</h3>

Phases 0–7 shipped dual-column `embedding_sync` for local, GCP, and API CRUD. AWS deploy bootstrap still used `load_openai_embeddings_to_pgvector_rds_api.py` writing legacy column `embedding` — broken after `001_embedding_profiles.sql`.

<h3 id="war-story-8-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.2 Root Cause</h3>

Bootstrap path was never ported when schema moved to `embedding_openai_1536` / `embedding_skylark_2048`. Deploy runs from laptop (no TCP to private Aurora); reusing psycopg2 `embedding_sync` in a one-off ECS task was rejected as extra infra.

<h3 id="war-story-8-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.3 Key Insight</h3>

Split **transport** from **orchestration**: `embedding_sync_core` holds the profile loop; `embedding_sync_rds` implements `execute_statement` UPDATEs. Bootstrap = Data API from outside VPC; steady-state CRUD = ECS psycopg2 — same storage rules, different wire.

<h3 id="war-story-8-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.4 Resolution</h3>

Refactored RDS ETL: scalars → `sync_all_embeddings_rds`. `setup_database.py` applies migration 001, verifies `embedding_openai_1536`, passes `ARK_*` to ETL. ECS nonkube gets `ark_api_key` Secrets Manager + ModelArk env vars.

<h3 id="war-story-8-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.5 Takeaway</h3>

When the same business logic must run over RDS Data API and psycopg2, extract a transport-agnostic core and test both adapters — do not fork the profile loop. Match the existing deploy workflow (laptop + HTTPS) before adding VPC one-off tasks.

<h2 id="war-story-9-llm-inference-env" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">9. LLM_INFERENCE_PROVIDER: .env value ignored in Docker nonkube</h2>

**creation:** 260521 · **last_updated:** 260521 · **keywords:** LLM_INFERENCE_PROVIDER, ModelArk, docker-compose, env contract, chat provider, claude · **difficulty:** 5 · **significance:** 7

<h3 id="war-story-9-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.1 Context</h3>

Phase 3 added `if LLM_INFERENCE_PROVIDER=modelark` in `client_factory.py`. Operators set `modelark` in root `.env` expecting BytePlus chat, but local Docker nonkube still used Claude.

<h3 id="war-story-9-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.2 Root Cause</h3>

`docker-compose.nonkube.yml` never passed `LLM_INFERENCE_PROVIDER` into the API container — only vars explicitly listed in `environment:` reach the process. The knob was documented as “optional” under the BytePlus block, so unset-vs-claude semantics were implicit.

<h3 id="war-story-9-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.3 Key Insight</h3>

Chat inference is a **fourth axis** orthogonal to `EMBEDDING_ACTIVE_PROFILE`. A boolean-style env check is not enough: need an allowlist (`claude` | `modelark`, default `claude`), central resolver (`llm_inference_config.py`), and **deploy wiring** (compose, kube j2, Terraform) so runtime matches `.env`.

<h3 id="war-story-9-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.4 Resolution</h3>

Added `get_llm_inference_provider()`, refactored factory dispatch, dedicated envex section, compose `${LLM_INFERENCE_PROVIDER:-claude}`, kube/terraform env vars, doctor branches per provider, `/health` and `/version` expose resolved provider.

<h3 id="war-story-9-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.5 Takeaway</h3>

For every operator-facing env knob, trace **.env → deploy manifest → container env → factory**. If any hop is missing, the feature works in direct `python` runs but fails in Docker — add a static compose/k8s unit test that asserts the key is declared.

---

<h2 id="war-story-10-spark-bootstrap-oom" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">10. Local Spark bootstrap exit 137 — shared Docker RAM and host schedulers</h2>

**creation:** 260613 · **last_updated:** 260613 · **keywords:** Spark, Docker Desktop, OOM, exit 137, scheduler_local, docker run, batch_analytics, local nonkube · **difficulty:** 7 · **significance:** 8

<h3 id="war-story-10-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">10.1 Context</h3>

After a full local `scope=all` deploy with `--force-refresh-data` and `--force-build`, embedding sync succeeded (400 vectors, 200 rows), but Spark bootstrap failed with a single line: `[ERROR] Spark bootstrap failed`. The Batch Analytics UI showed “No analytics data available yet.” Chat and ModelArk query paths worked; only the batch pipeline was missing.

Deploy had run `tools/local/nonkube/deploy_nonkube.py`, which executes:

```bash
docker run --rm ... fru-spark:local spark-submit ... /opt/fru/jobs/run_analytics.py
```

Logs showed Spark starting (`[STEP] FRU Batch Analytics START`, Delta writes, stage 11 at ~32/50 tasks) then silence — no Python traceback.

<h3 id="war-story-10-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">10.2 Root Cause</h3>

Reproduction confirmed **exit code 137** (SIGKILL). On Docker Desktop the VM has ~**7.65 GiB** total memory shared by API, Postgres, and every Spark container.

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Contributor</th><th style="padding:8px">What happened</th><th style="padding:8px">Effect</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Per-tick <code>docker run</code></strong></td><td style="background:#fff3e0;padding:8px"><code>scheduler_local.py</code> launches a <strong>new</strong> JVM every <code>ANALYTICS_SCHEDULER_INTERVAL_SECONDS</code> (default 180s)</td><td style="background:#ffebee;padding:8px">Each container ~1.8–2.0 GiB while running</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>No Forbid</strong></td><td style="background:#fff3e0;padding:8px">Scheduler does not check if a previous Spark container is still alive</td><td style="background:#ffebee;padding:8px">Job &gt; 3 min → overlapping containers</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Duplicate schedulers</strong></td><td style="background:#fff3e0;padding:8px">Multiple <code>start_local</code> runs left <strong>3</strong> <code>scheduler_local.py</code> PIDs on the host</td><td style="background:#ffebee;padding:8px">3× tick rate → more concurrent <code>docker run</code></td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Zombie Spark containers</strong></td><td style="background:#fff3e0;padding:8px">16-hour-old <code>fru-spark:local</code> containers still holding ~3.6 GiB</td><td style="background:#ffebee;padding:8px">Less headroom for bootstrap</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Bootstrap race</strong></td><td style="background:#fff3e0;padding:8px">Deploy bootstrap concurrent with scheduler-triggered runs</td><td style="background:#ffebee;padding:8px">Bootstrap is the run that loses the OOM lottery</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Delta bloat (secondary)</strong></td><td style="background:#fff3e0;padding:8px"><code>fru_delta</code> not wiped on <code>--force-refresh-data</code>; 257 parquet files, version ~28</td><td style="background:#fff3e0;padding:8px">Heavier scans; not primary kill signal</td></tr>
</tbody>
</table>

The deploy script only checked subprocess return code and logged a generic error — **137 was never surfaced**, so the failure looked like a Spark logic bug.

<h3 id="war-story-10-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">10.3 Key Insight</h3>

<span style="background:#e8f5e9;padding:2px 6px">Exit 137 on local Spark almost always means Docker OOM on a **shared-RAM laptop**, not a bug in <code>run_analytics.py</code>.</span>

Ask: how many `fru-spark:local` containers are running? How many `scheduler_local.py` processes? What does `docker stats` show against the ~7.6 GiB cap?

<h3 id="war-story-10-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">10.4 Resolution</h3>

**Immediate workaround (verified):**

```bash
pkill -f 'tools/local/scheduler_local.py'
docker ps -q --filter ancestor=fru-spark:local | xargs docker stop
# single bootstrap run → ~2 min, success
```

`/analytics` then returned `total_records: 200`.

**Planned structural fix:** refactor to Compose `analytics-worker` singleton — see [war story 11](#war-story-11-analytics-worker-design) and plan `REFACTOR_LOCAL_NONKUBE_SPARK_ANALYTICS_WORKER.md`.

```mermaid
flowchart LR
  subgraph problem["Failure mode"]
    S1["scheduler tick"]
    S2["scheduler tick"]
    B["bootstrap docker run"]
    S1 --> C1["container ~2GiB"]
    S2 --> C2["container ~2GiB"]
    B --> C3["container ~2GiB"]
    C1 --> OOM["Host OOM → 137"]
    C2 --> OOM
    C3 --> OOM
  end
```

<h3 id="war-story-10-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">10.5 Takeaway</h3>

When local Spark dies mid-log with no traceback, check **exit 137** and **container count** before debugging Delta or SQL. Band-aid cleanup before bootstrap helps once; steady state needs a **single scheduler owner** with Forbid semantics.

---

<h2 id="war-story-11-analytics-worker-design" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">11. Compose analytics-worker — singleton owner for local nonkube Spark</h2>

**creation:** 260613 · **last_updated:** 260613 · **keywords:** design, system design, Spark, docker compose, local nonkube, scheduler, concurrency Forbid, batch_analytics · **difficulty:** 6 · **significance:** 8

<h3 id="war-story-11-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">11.1 Context</h3>

Local nonkube was meant to mirror cloud: “API in a container + scheduled Spark.” Cloud uses **platform schedulers** (EventBridge, Cloud Scheduler, K8s CronJob). Local implemented scheduling as a **Python script on the Mac host** that shells out to `docker run` — creating a second, unofficial control plane with no replica limit and no overlap policy.

Local **kube** scope already had the right pattern: `spark-cronjob.yaml.j2` sets `concurrencyPolicy: Forbid`. Local **nonkube** did not.

<h3 id="war-story-11-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">11.2 Root Cause</h3>

**Architectural mismatch:** treating the laptop host as a mini-Kubernetes.

| Anti-pattern | Why it fails locally |
|--------------|----------------------|
| Host-owned scheduler | Duplicate PIDs when operators re-run `start_local` |
| `docker run` per job | Full JVM cold start + separate memory accounting per container |
| Three entry points (deploy, start_local, scheduler) | No single source of truth for “is Spark running?” |
| Bootstrap = another `docker run` | Races scheduled ticks during deploy |

<h3 id="war-story-11-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">11.3 Key Insight</h3>

<span style="background:#e8f5e9;padding:2px 6px">Local nonkube needs **one Compose service** that owns Spark scheduling — same *role* as kube CronJob, different *packaging* because Docker Desktop shares RAM.</span>

Mental model alignment with cloud:

- **Same job code:** `run_analytics.py`
- **Same phases:** bootstrap once, then schedule
- **Different wrapper:** persistent worker with in-process `spark-submit` + Forbid, not host `docker run`

<h3 id="war-story-11-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">11.4 Resolution</h3>

**Target architecture** (plan: `REFACTOR_LOCAL_NONKUBE_SPARK_ANALYTICS_WORKER.md`):

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px">Step</th><th style="padding:8px">Mechanism</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px">1</td><td style="background:#e8f5e9;padding:8px"><code>docker compose up -d postgres api</code></td></tr>
<tr><td style="background:#e3f2fd;padding:8px">2</td><td style="background:#e8f5e9;padding:8px"><strong>Bootstrap:</strong> <code>compose run --rm analytics-worker --once</code></td></tr>
<tr><td style="background:#e3f2fd;padding:8px">3</td><td style="background:#e8f5e9;padding:8px"><strong>Schedule:</strong> <code>compose up -d analytics-worker</code> (loop + Forbid)</td></tr>
<tr><td style="background:#e3f2fd;padding:8px">Retire</td><td style="background:#fff3e0;padding:8px"><code>scheduler_local.py</code> for nonkube; no host <code>docker run</code></td></tr>
</tbody>
</table>

```mermaid
flowchart TB
  PG["postgres"]
  API["api nonkube"]
  AW["analytics-worker x1"]
  PG --> AW
  PG --> API
  AW -->|"if child alive: SKIP"| FORBID{"Forbid"}
  FORBID -->|"else"| SS["spark-submit run_analytics.py"]
  SS --> DB["batch_analytics"]
  SS --> DELTA["fru_delta volume"]
```

**Forbid rule:** if previous `spark-submit` subprocess still running at tick time, log skip and wait — equivalent to kube `concurrencyPolicy: Forbid`.

**Cleanup vs Forbid (complementary, not either/or):**

| Layer | When | What |
|-------|------|------|
| Deploy cleanup | Bootstrap time | Ensure no orphan containers before `--once` |
| Worker Forbid | Every tick | Prevent overlap while worker is the sole owner |
| Compose replicas = 1 | Always | Prevent duplicate worker services |

<h3 id="war-story-11-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">11.5 Takeaway</h3>

Do not patch local Spark with “kill zombies before deploy” alone. Give local nonkube a **first-class Compose scheduler** with Forbid — the same invariant kube already has — and delete host-side `docker run` loops.

---

<h2 id="war-story-12-local-vs-cloud-spark-scheduling" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">12. Why local uses a persistent worker but cloud keeps ephemeral tasks</h2>

**creation:** 260613 · **last_updated:** 260613 · **keywords:** design, system design, Spark, local dev, AWS ECS, GCP Cloud Run, Fargate, memory, scheduling · **difficulty:** 5 · **significance:** 7

<h3 id="war-story-12-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">12.1 Context</h3>

After diagnosing local Spark OOM, we proposed a **Compose analytics-worker** (one container, loop inside, Forbid). A natural question: should AWS/GCP nonkube adopt the same pattern “for free” when we fix local?

**Answer: no.** Cloud already schedules Spark correctly for its constraints. Local needs a different wrapper for **different hardware economics**.

<h3 id="war-story-12-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">12.2 Root Cause of the confusion</h3>

Both environments use “one Spark run = one container,” so they **look** the same. The difference is **who pays for memory and how it is isolated**:

<table>
<thead>
<tr style="background:#1565c0;color:white"><th style="padding:8px"></th><th style="padding:8px">Local laptop</th><th style="padding:8px">Cloud (AWS/GCP nonkube)</th></tr>
</thead>
<tbody>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Memory model</strong></td><td style="background:#ffebee;padding:8px">**Shared pool** — Docker Desktop ~7.6 GiB for API + DB + N Spark JVMs</td><td style="background:#e8f5e9;padding:8px">**Per task** — Fargate / Cloud Run job gets its own limit (e.g. 2–4 GiB)</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Overlap failure</strong></td><td style="background:#ffebee;padding:8px">OOM kill (exit 137) — system crash</td><td style="background:#fff3e0;padding:8px">Extra cost, redundant writes — usually **no shared-node crash**</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Scheduler</strong></td><td style="background:#ffebee;padding:8px">Host script (fragile)</td><td style="background:#e8f5e9;padding:8px">EventBridge / Cloud Scheduler (managed)</td></tr>
<tr><td style="background:#e3f2fd;padding:8px"><strong>Idle cost</strong></td><td style="background:#e8f5e9;padding:8px">Laptop already on — worker RAM is “free” vs 3 JVMs</td><td style="background:#ffebee;padding:8px">24/7 worker = continuous billing; ephemeral = pay per run</td></tr>
</tbody>
</table>

<h3 id="war-story-12-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">12.3 Key Insight</h3>

**Analogy:**

- **Local** = one small kitchen. Multiple full-size ovens at once overflow the counter → fire marshal (Docker) shuts one down.
- **Cloud** = catering company that **rents one oven per job**. Two jobs at once costs double rent but does not collapse the building.

So local optimizes for **minimum concurrent JVMs** (singleton worker). Cloud optimizes for **platform-native ephemeral tasks** (already implemented in OpenTofu modules).

<h3 id="war-story-12-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">12.4 Resolution</h3>

**What stays on cloud (no change from local refactor):**

| Provider | Bootstrap | Schedule | Overlap |
|----------|-----------|----------|---------|
| AWS nonkube | ECS `run-task` once | EventBridge → RunTask | Allowed; isolated Fargate |
| GCP nonkube | `gcloud run jobs execute` | Cloud Scheduler → same job | Independent executions |
| AWS/GCP kube | K8s Job | CronJob `Forbid` | Built-in |

**What changes locally only:** Compose `analytics-worker` replaces `scheduler_local.py` + `docker run`.

**Optional cloud hardening (deferred):** AWS Step Functions guard or GCP “skip if execution running” — cost/ops optimization, not correctness.

```mermaid
flowchart LR
  subgraph local["Local — cap RAM"]
    W["1 worker container"]
    W --> J1["spark-submit"]
  end
  subgraph cloud["Cloud — rent per run"]
    EB["EventBridge / Scheduler"]
    EB --> T1["task 1"]
    EB --> T2["task 2 optional"]
  end
```

<h3 id="war-story-12-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">12.5 Takeaway</h3>

Same `run_analytics.py`, different schedulers: local needs a **memory-bounded singleton**; cloud needs **managed ephemeral tasks**. Porting the worker to AWS/GCP would add idle cost without fixing a problem Fargate already avoids.

---

<h2 id="war-story-13-local-dual-ui-entry" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">13. Local nonkube — two UI entry points (Vite vs nginx bundle)</h2>

**creation:** 260613 · **last_updated:** 260613 · **keywords:** local dev, nginx, Vite, Docker Compose, UX, cloud parity, /version, APP_IMAGE_TAG · **difficulty:** 3 · **significance:** 6

<h3 id="war-story-13-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">13.1 Context</h3>

Operators opened `http://localhost:5001/` and saw the full Chat UI while deploy docs called 5001 “the API.” The config strip showed `Build: [unknown]` and Batch Analytics ↻ gave no hint that reload does not run Spark. Both 5174 (Vite) and 5001 showed `Scope: nonkube`, which felt redundant.

<h3 id="war-story-13-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">13.2 Root Cause</h3>

Local nonkube intentionally **mirrors cloud**: one container image runs nginx on the published port, serves the baked SPA, and proxies API routes to Flask on an internal port (`core_app/nginx.conf`). Separately, `start_local.py` runs Vite on another port for hot reload — a **second** entry point that was under-documented.

| URL | Actual role |
|-----|-------------|
| **5001** | Production-style bundle (UI + API) |
| **5174** | Dev Vite → proxies to 5001 |

`APP_IMAGE_TAG` was not passed into Compose, so `/version` fell back to `[unknown]`. The ↻ button only called `GET /analytics` (PostgreSQL snapshot) with no in-panel explanation.

<h3 id="war-story-13-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">13.3 Key Insight</h3>

**Cloud parity creates local confusion unless you name both entry points.** Keeping 5001 published is correct for curl, integration tests, and bundled smoke; dev work should be steered to Vite via logs, docs, and an in-app banner when `import.meta.env.DEV` is false on local nonkube.

<h3 id="war-story-13-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">13.4 Resolution</h3>

| Change | Purpose |
|--------|---------|
| `generate_image_tag("local")` → `APP_IMAGE_TAG` in deploy + compose | Meaningful `Build:` line |
| `/version` adds chat/embedding model fields + `dev_frontend_port` | Config strip + banner port from API |
| `/analytics` `meta.reload_does` / `reload_does_not` | Batch Analytics ↻ expectations |
| Deploy logs distinguish API (nginx+Flask) vs Vite | Operator clarity |
| `docs/learned/local/LOCAL_PORTS_AND_UI_ENTRY_POINTS.md` | Canonical port guide |

Scope label duplication (5174 vs 5001 both `nonkube`) was **deferred** — correct behavior, not a bug.

<h3 id="war-story-13-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">13.5 Takeaway</h3>

When a dev stack copies cloud’s “single container UI+API,” add an explicit **dev overlay** (Vite) and document both URLs. Treat `/version` as the UI’s source of truth for build stamp and runtime config hints.

---

<h2 id="war-story-14-playwright-e2e-scenarios" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">14. Playwright E2E — shared scenarios, F900 CRUD, batch panel ≠ chat path</h2>

**creation:** 260614 · **last_updated:** 260614 · **keywords:** Playwright, e2e, pytest layout, scenarios, F900, CRUD, batch analytics, external stack · **difficulty:** 3 · **significance:** 5

<h3 id="war-story-14-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">14.1 Context</h3>

FRU had solid pytest unit/integration coverage but no browser package. Product wanted five demo-grade flows (four chat queries + one Data Management CRUD loop) reusable in CI specs and stakeholder demos.

<h3 id="war-story-14-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">14.2 Root Cause</h3>

Without a shared scenario module, Playwright specs and demo scripts duplicate query strings and expectations — drift is guaranteed. S5 (insert $70k NYC sale, ask “best city”) tempts testers to assert on the Batch Analytics ↻ panel, but that panel reloads the **last Spark snapshot**, not live `/rawdata` rows.

<h3 id="war-story-14-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">14.3 Key Insight</h3>

Mirror portuguese-learn’s layering: **L0** UI locators, **L1** domain runners, **`support/scenarios.ts`** as the only catalog. Run against **external stack** (`PLAYWRIGHT_EXTERNAL_STACK=1`) on Vite port **5174**. Reserve **`F900`** above seed `F001–F200` for mutable CRUD e2e; always pre-delete and `finally` cleanup.

<h3 id="war-story-14-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">14.4 Resolution</h3>

| Piece | Location |
|-------|----------|
| Integration pytest subfolders | `tests/integration/{api,crud,embeddings,verify}/` |
| Playwright package | `tests/e2e/` — `workers: 1`, soft LLM assertions |
| Scenarios S1–S5 | `tests/e2e/support/scenarios.ts` |
| Demo tour | `demos/playwright_e2e/sequences/analytics_assistant_tour.spec.ts` |
| Run wrappers | `scripts/run_e2e_tests.sh`, `demos/playwright_e2e/scripts/run_demo.sh` |

S5 e2e hard-asserts **grid row + chat answer (`new york`)**; Batch Analytics ↻ is **demo-only smoke**.

<h3 id="war-story-14-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">14.5 Takeaway</h3>

Treat browser e2e as a **third test category** with shared scenario data, not one-off specs. For CRUD → analytics stories, assert the **agent/SQL path** the user actually queries, not the Spark batch panel, unless you run a fresh batch job.

---

<h2 id="war-story-15-model-stack-catalog" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">15. Model stack catalog — embed filters chat, display parity in execution log</h2>

**creation:** 260615 · **last_updated:** 260615 · **keywords:** design, model catalog, stacks, YAML, SSE model_context, execution log, Bedrock multi-model, deploy wiring · **difficulty:** 4 · **significance:** 6

<h3 id="war-story-15-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">15.1 Context</h3>

Per-request **Embedded Model** and **Chat Model** dropdowns were independent. Users could pick `skylark_2048` + `claude_haiku` — a pair that cannot work (different embed columns and inference vendors). The execution log showed logical ids (`openai_1536`) while the header showed human model slugs (`text-embedding-3-small`).

<h3 id="war-story-15-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">15.2 Root Cause</h3>

The first catalog pass listed **embeddings** and **chat** separately with no **allowlist of pairs**. The UI and SSE reused different fields: dropdown labels came from YAML `display`, but the log rendered `embedding_profile`. Bedrock used one global inference profile env var, so multiple Claude tiers could not be selected on AWS even if the dropdown showed them.

<h3 id="war-story-15-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">15.3 Key Insight</h3>

Treat **stacks** as the product contract: `(embedding_profile, chat_choice)` rows in YAML, filtered by cloud + creds + pgvector population, exposed as `stacks[]` on `/model-catalog`. One resolver — `resolve_chat_model_id` — feeds agent, SQL tool, doctor, and verify scripts. **Display strings** are the only user-facing labels in header and execution log; logical ids stay in query params and ops logs.

<h3 id="war-story-15-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">15.4 Resolution</h3>

| Layer | Change |
|-------|--------|
| YAML | `stacks:` + chat `model_id` / `bedrock_model_id` per profile |
| API | `resolve_request_model_context` rejects invalid pairs (400); SSE `model_context` sends `embedding_display` / `chat_display` |
| UI | Embed change recomputes allowed chat ids from `catalog.stacks` |
| Bedrock | Per-request `model_id` overrides global inference profile when set |
| Deploy | `expand_model_defaults_for_deploy()` passes `DEFAULT_*` + `ALLOW_PER_REQUEST_MODEL_OVERRIDE` through compose, kube j2, AWS/GCP Terraform |

<h3 id="war-story-15-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">15.5 Takeaway</h3>

When the UI exposes **two** model pickers that must compose a valid runtime stack, do not rely on client-side discipline alone — ship a **server-driven allowlist**, cascade the dependent dropdown, and use the **same display resolver** everywhere the user reads model names (header, execution log, doctor errors).
