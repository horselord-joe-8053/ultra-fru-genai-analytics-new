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
- The JSON is **tree-structured**; for **correct order** and **multimodal** messages, use **`linear_conversation`** and the rules in **`chatgpt/playwright/extract_transcript.mjs`** (a naive `mapping` loop is not enough).
- **Live fetch** from automation often hits **403** / Cloudflare; the repo’s working path is **Playwright** in **`chatgpt/playwright/`** (see HOWTO).
- Once extracted, we could:
  - Rephrase and integrate the CI/CD + feature-flag insights into our own docs (`TODO_LEARNED_CICD.md`).
  - Keep our documentation **self-contained**, without relying on the external share remaining live.

This pattern is reusable any time we need to mine a shared ChatGPT conversation for architecture notes, war stories, or reference material.

**HOWTO + tooling:** [chatgpt/HOWTO_EXTRACT_CHATGPT.md](chatgpt/HOWTO_EXTRACT_CHATGPT.md) · [chatgpt/playwright/](chatgpt/playwright/) (`fetch_share.mjs`, `extract_transcript.mjs`)


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
