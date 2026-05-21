<h1 id="war-stories-gcp-title" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">WAR_STORIES_GCP</h1>

A curated list of **non-trivial technical war stories**, capturing real lessons suitable for **senior-level interviews**.

**Authoring discipline:** `.cursor/rules/exwar-war-stories-extraction.mdc` and `.cursor/rules/mrkd-markdown-authoring.mdc`.

**GCP-Specific War Stories**

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
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">1</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-1">1. Unified Google Gen AI SDK: One Interface, Two Auth Paths</a></td><td style="padding:8px;background:#fff3e0">Unified Google Gen AI SDK: One Interface, Two Auth Paths</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">2</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-2">2. Anthropic Claude 529 Overloaded: Intermittent Failures, Alternative Models, and Retriable vs Non-Retriable Errors</a></td><td style="padding:8px;background:#e8f5e9">Anthropic Claude 529 Overloaded: Intermittent Failures, Alternative Models, and Retriable vs Non-Retriable…</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">3</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-3">3. Cloud Run → Cloud SQL: VPC Connector Required (Unlike ECS in VPC)</a></td><td style="padding:8px;background:#fff3e0">Cloud Run → Cloud SQL: VPC Connector Required (Unlike ECS in VPC)</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">4</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-4">4. GCS vs S3 State Backend: GCS Has Built-in Locking (No DynamoDB)</a></td><td style="padding:8px;background:#e8f5e9">GCS vs S3 State Backend: GCS Has Built-in Locking (No DynamoDB)</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">5</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-5">5. Artifact Registry vs ECR: Different Image Paths and Auth</a></td><td style="padding:8px;background:#fff3e0">Artifact Registry vs ECR: Different Image Paths and Auth</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">6</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-6">6. GCP Required APIs: Enable Before First Deploy</a></td><td style="padding:8px;background:#e8f5e9">GCP Required APIs: Enable Before First Deploy</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">7</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-7">7. GCP State Bucket Naming: project_id vs account_id</a></td><td style="padding:8px;background:#fff3e0">GCP State Bucket Naming: project_id vs account_id</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">8</td><td style="padding:8px;background:#e8f5e9"><a href="#war-story-8">8. Service Networking Peering Teardown: Compute API vs Service Networking API</a></td><td style="padding:8px;background:#e8f5e9">Service Networking Peering Teardown: Compute API vs Service Networking API</td></tr>
<tr><td style="background:#e3f2fd;padding:8px;text-align:right">9</td><td style="padding:8px;background:#fff3e0"><a href="#war-story-9">9. Smart DB Loading Strategy: Verify-Only Fallback Instead of Fail-Fast</a></td><td style="padding:8px;background:#fff3e0">Smart DB Loading Strategy: Verify-Only Fallback Instead of Fail-Fast</td></tr>
</tbody>
</table>

---

<h2 id="war-story-1" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">1. Unified Google Gen AI SDK: One Interface, Two Auth Paths</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Google Gen AI, python-genai, AI Studio, Vertex AI, authentication, unified SDK, Gemini
**difficulty:** 6
**significance:** 8

<h3 id="war-story-1-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.1 Context</h3>

In late 2024, Google launched the `google-genai` library ([github.com/googleapis/python-genai](https://github.com/googleapis/python-genai)), merging two previously separate Python APIs into one unified interface. Previously, developers used `google-generativeai` for AI Studio (Gemini Developer API) and `google-cloud-aiplatform` for Vertex AI—two different SDKs, two different call patterns. The new SDK handles both: once the client is initialized, `client.models.generate_content()` and `generate_content_stream()` are identical regardless of backend.

<h3 id="war-story-1-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.2 The Authentication Hurdle</h3>

**The critical gotcha:** AI Studio and Vertex AI use **different authentication mechanisms**, and the unified SDK does not hide this. Each backend has its own official way to authenticate and connect.

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Backend</th>
<th style="padding:8px">Auth</th>
<th style="padding:8px">Env vars (optional)</th>
<th style="padding:8px">Code</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>AI Studio</strong></td>
<td style="padding:8px;background:#e8f5e9">API key string</td>
<td style="padding:8px;background:#e8f5e9"><code>GEMINI_API_KEY</code> or <code>GOOGLE_API_KEY</code> (latter takes precedence)</td>
<td style="padding:8px;background:#e8f5e9"><code>genai.Client(api_key='...')</code> or <code>genai.Client()</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Vertex AI</strong></td>
<td style="padding:8px;background:#fff3e0">Service account / ADC</td>
<td style="padding:8px;background:#fff3e0"><code>GOOGLE_GENAI_USE_VERTEXAI=true</code>, <code>GOOGLE_CLOUD_PROJECT</code>, <code>GOOGLE_CLOUD_LOCATION</code></td>
<td style="padding:8px;background:#fff3e0"><code>genai.Client(vertexai=True, project='...', location='...')</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Vertex AI (org-restricted)</strong></td>
<td style="padding:8px;background:#e8f5e9">Explicit credentials</td>
<td style="padding:8px;background:#e8f5e9"><code>GOOGLE_APPLICATION_CREDENTIALS</code> + JSON key</td>
<td style="padding:8px;background:#e8f5e9">Load with <code>google.oauth2.service_account.Credentials.from_service_account_file()</code>; pass <code>credentials=creds</code></td>
</tr>
</tbody>
</table>

**Enterprise restriction:** Many GCP organizations disable Standard API Keys via org policy. In that case, you cannot use AI Studio's API key path; you must use Vertex AI with a service account.

<h3 id="war-story-1-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.3 Key Insight</h3>

> One SDK, two auth paths. The unified interface is a win—same `generate_content()` and `generate_content_stream()` calls—but you must explicitly choose and configure the auth path. Design your `client_factory` to branch on env vars (`GCP_LLM_USE_VERTEX_AI`, `GOOGLE_AI_API_KEY`) so switching is configuration-only.

<h3 id="war-story-1-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.4 Resolution</h3>

1. **AI Studio path:** `client = genai.Client(api_key='...')` or set `GEMINI_API_KEY` / `GOOGLE_API_KEY`.
2. **Vertex AI path (ADC):** `client = genai.Client(vertexai=True, project='...', location='...')`—SDK uses `GOOGLE_APPLICATION_CREDENTIALS` or GKE/VM metadata.
3. **Vertex AI path (org-restricted):** Load credentials with `google.oauth2.service_account.Credentials.from_service_account_file(path, scopes=['https://www.googleapis.com/auth/cloud-platform'])` and pass `credentials=creds`.

<h3 id="war-story-1-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">1.5 Takeaway</h3>

For GCP LLM readiness: (1) Use `google-genai` for both AI Studio and Vertex AI. (2) Start with AI Studio (API key) for simplicity; upgrade to Vertex AI when compliance or Workload Identity is required. (3) Never hardcode which backend to use—branch on env vars. (4) In VMs/containers on GCP, Vertex AI with Workload Identity or ADC auto-authenticates and auto-refreshes tokens; no JSON key needed. See `docs/REFACTOR_PLAN_GCP_READINESS.md` for the full plan.

---

<h2 id="war-story-2" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">2. Anthropic Claude 529 Overloaded: Intermittent Failures, Alternative Models, and Retriable vs Non-Retriable Errors</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Anthropic, Claude API, 529 overloaded_error, intermittent failures, model fallback, retriable errors, verify polling
**difficulty:** 6
**significance:** 7

<h3 id="war-story-2-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.1 Context</h3>

During GCP deploy verification, the QueryStream endpoint repeatedly failed with:

```json
{"message": "Agent processing failed: Error code: 529 - {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}, 'request_id': '...'}"}
```

Deploy succeeded; verify failed. A single-call model test (`test_available_model.py`) sometimes passed, giving a false sense that the setup was fine. At other times, 10 consecutive calls with 2s intervals produced 8× 529 and 2× 500 errors—zero successes. The problem was intermittent and model-specific: `claude-haiku-4-5` (the default) was heavily overloaded.

<h3 id="war-story-2-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.2 Root Cause</h3>

Anthropic's API returns **529 (Overloaded)** and **500 (Internal server error)** when capacity is saturated. These are **transient**—retrying later often succeeds. The popular `claude-haiku-4-5` model sees the most traffic and overloads first. Older or higher-tier models (Sonnet, Opus) share different capacity pools and can remain available when Haiku 4.5 is overloaded.

Our verify script initially treated any error event in the SSE stream as non-retriable and failed fast. That was correct for 404 (model not found) and auth errors, but wrong for 529/500—those should keep polling.

<h3 id="war-story-2-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.3 Alternative Models and Comparison</h3>

We tested four Claude models for availability and overload resistance:

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Model</th>
<th style="padding:8px">Input ($/MTok)</th>
<th style="padding:8px">Output ($/MTok)</th>
<th style="padding:8px">Latency (1 call)</th>
<th style="padding:8px">Relative speed</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>claude-haiku-4-5</strong></td>
<td style="padding:8px;background:#e8f5e9">$1.00</td>
<td style="padding:8px;background:#e8f5e9">$5.00</td>
<td style="padding:8px;background:#e8f5e9">~0.68s</td>
<td style="padding:8px;background:#e8f5e9">Fastest (~49 tok/s)</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>claude-3-haiku-20240307</strong></td>
<td style="padding:8px;background:#fff3e0">$0.25</td>
<td style="padding:8px;background:#fff3e0">$1.25</td>
<td style="padding:8px;background:#fff3e0">~0.78s</td>
<td style="padding:8px;background:#fff3e0">Fast</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>claude-sonnet-4-5</strong></td>
<td style="padding:8px;background:#e8f5e9">$3.00</td>
<td style="padding:8px;background:#e8f5e9">$15.00</td>
<td style="padding:8px;background:#e8f5e9">~1.75s</td>
<td style="padding:8px;background:#e8f5e9">Medium (~20 tok/s)</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>claude-opus-4-5</strong></td>
<td style="padding:8px;background:#fff3e0">$5.00</td>
<td style="padding:8px;background:#fff3e0">$25.00</td>
<td style="padding:8px;background:#fff3e0">~1.86s</td>
<td style="padding:8px;background:#fff3e0">Slower (~19 tok/s)</td>
</tr>
</tbody>
</table>

**Cost (1M in + 1M out):** Haiku 4.5 $6, Haiku 3 $1.50, Sonnet 4.5 $18, Opus 4.5 $30. `claude-3-haiku-20240307` is 4× cheaper than Haiku 4.5 but deprecated (retires April 2026).

**Best choices by criterion:**
- **Fastest:** claude-haiku-4-5
- **Cheapest:** claude-3-haiku-20240307
- **Most capable:** claude-opus-4-5
- **Fallback when Haiku overloads:** claude-3-haiku-20240307 or claude-sonnet-4-5

<h3 id="war-story-2-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.4 Resolution</h3>

1. **Verify script:** Updated `_is_non_retriable_query_error()` to treat `overloaded_error`, `api_error`, `rate_limit`, and `internal server error` as **retriable**. Verify now keeps polling instead of failing fast on 529/500.

2. **Reproducibility test:** Added `tools/gcp/standalone/temp_one_off/test_overload_529.py`—10 consecutive calls with 2s interval—to reproduce intermittent overload. Single-call tests are insufficient.

3. **Multi-model tests:** Extended `test_available_model.py` and `test_overload_529.py` to run against all four models with well-formatted logging and a final summary table.

4. **Fallback strategy:** Documented alternative models. When `claude-haiku-4-5` is overloaded, switch `CLAUDE_MODEL` in `.env` to `claude-3-haiku-20240307` (cheapest) or `claude-sonnet-4-5` (more capable) and redeploy.

<h3 id="war-story-2-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">2.5 Takeaway</h3>

(1) Anthropic 529/500 are transient—treat them as retriable in verify and retry logic. (2) Single-call model tests can pass during brief windows; use consecutive-call tests to catch intermittent overload. (3) Keep a list of fallback models (older Haiku, Sonnet, Opus) and switch via env when the default is overloaded. (4) Distinguish non-retriable errors (404, auth) from retriable ones (529, 500, rate limit) so you fail fast on config bugs but keep polling on capacity issues.

---

<h2 id="war-story-3" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">3. Cloud Run → Cloud SQL: VPC Connector Required (Unlike ECS in VPC)</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Cloud Run, Cloud SQL, VPC connector, Serverless VPC Access, private IP, Terraform wiring
**difficulty:** 7
**significance:** 9

<h3 id="war-story-3-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.1 Context</h3>

On AWS, ECS Fargate tasks run **inside** the VPC. They reach Aurora via private IP directly. On GCP, Cloud Run runs **outside** the VPC by default. Cloud SQL has a private IP inside your VPC. Without a bridge, the API container cannot reach the database.

<h3 id="war-story-3-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.2 Root Cause</h3>

Cloud Run is a serverless platform that runs containers in Google-managed infrastructure. It does not automatically join your VPC. Cloud SQL uses Private Service Access to get a private IP in your VPC. To connect them, you need a **Serverless VPC Access connector**—a small subnet (e.g. 10.126.0.0/28) that acts as a bridge between Cloud Run and your VPC.

```mermaid
%%{init: {'themeVariables': {'fontSize': '9px'}}}%%
flowchart LR
    subgraph EXT["Cloud Run (outside VPC)"]
        API["API<br/>PGHOST=10.50.0.3"]
    end
    subgraph BRIDGE["VPC Connector"]
        CONN["10.126.0.0/28<br/>bridge"]
    end
    subgraph VPC["Your VPC"]
        SQL["Cloud SQL<br/>10.50.0.3"]
    end
    API -->|"① TCP"| CONN
    CONN -->|"② via connector"| SQL
    SQL -->|"③ OK"| API
```

<h3 id="war-story-3-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.3 Terraform Wiring</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Stack</th>
<th style="padding:8px">Creates</th>
<th style="padding:8px">Outputs</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>durable</strong></td>
<td style="padding:8px;background:#e8f5e9">VPC, Private Service Access, Cloud SQL, VPC connector</td>
<td style="padding:8px;background:#e8f5e9"><code>vpc_connector_id</code>, <code>cloud_sql_private_ip</code>, <code>cloud_sql_database_name</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>nonkube</strong></td>
<td style="padding:8px;background:#fff3e0">Cloud Run module</td>
<td style="padding:8px;background:#fff3e0">Reads <code>remote_state.shared_durable</code>; passes <code>vpc_connector_id</code>, <code>env_vars</code> (PGHOST, PGPORT, ...), <code>secret_ids</code> (PGPASSWORD)</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>cloud_run module</strong></td>
<td style="padding:8px;background:#e8f5e9"><code>vpc_access { connector = vpc_connector_id, egress = PRIVATE_RANGES_ONLY }</code></td>
<td style="padding:8px;background:#e8f5e9">Enables egress to private IPs via connector</td>
</tr>
</tbody>
</table>

<h3 id="war-story-3-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.4 Key Insight</h3>

> Cloud Run is not in VPC like ECS Fargate. You must create a VPC connector in the durable stack and pass it to Cloud Run. Set `vpc_access.egress = PRIVATE_RANGES_ONLY` so traffic to 10.x.x.x goes through the connector. See `docs/learned/cloud_shared/GCP_API_CLOUD_SQL_WIRING.md`.

<h3 id="war-story-3-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">3.5 Takeaway</h3>

(1) Durable stack creates VPC connector; nonkube stack passes it to Cloud Run. (2) Cloud Run Job (Spark) needs the same connector to reach Cloud SQL. (3) Without `vpc_access`, Cloud Run would try to reach 10.50.0.3 over the public internet and fail. (4) Reference: `docs/learned/cloud_shared/GCP_API_CLOUD_SQL_WIRING.md`.

---

<h2 id="war-story-4" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">4. GCS vs S3 State Backend: GCS Has Built-in Locking (No DynamoDB)</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Terraform, OpenTofu, state backend, GCS, S3, DynamoDB, locking
**difficulty:** 5
**significance:** 7

<h3 id="war-story-4-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.1 Context</h3>

AWS Terraform state uses **S3 + DynamoDB**: S3 stores the state file; DynamoDB provides locking to prevent concurrent runs from corrupting state. GCP uses **GCS** for state. GCS has **built-in locking**—no separate lock table required.

<h3 id="war-story-4-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.2 Comparison</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Aspect</th>
<th style="padding:8px">AWS</th>
<th style="padding:8px">GCP</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>State storage</strong></td>
<td style="padding:8px;background:#e8f5e9">S3 bucket</td>
<td style="padding:8px;background:#e8f5e9">GCS bucket</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Locking</strong></td>
<td style="padding:8px;background:#fff3e0">DynamoDB table (separate)</td>
<td style="padding:8px;background:#fff3e0">Built into GCS backend</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Backend block</strong></td>
<td style="padding:8px;background:#e8f5e9"><code>backend "s3" { bucket, key, dynamodb_table, region }</code></td>
<td style="padding:8px;background:#e8f5e9"><code>backend "gcs" { bucket, prefix }</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Bootstrap</strong></td>
<td style="padding:8px;background:#fff3e0">Create S3 bucket + DynamoDB table</td>
<td style="padding:8px;background:#fff3e0">Create GCS bucket only</td>
</tr>
</tbody>
</table>

<h3 id="war-story-4-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.3 Key Insight</h3>

> When implementing GCP, do not copy `dynamodb_table` or `dynamodb_table_name` from AWS. GCS backend uses `prefix` (e.g. `fru/dev/us-central1/gcp-shared-durable.tfstate`) and handles locking internally. Bootstrap state backend for GCP: create only the GCS bucket.

<h3 id="war-story-4-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">4.4 Takeaway</h3>

(1) `tools/gcp/scope_shared/deploy/setup_state_backend.py` creates only the GCS bucket. (2) `backend_config()` in `terra_init.py` must pass `backend="gcs"` and `bucket`, `prefix`—no `dynamodb_table`. (3) State key format: `{prefix}/{env}/{region}/{stack_id}.tfstate` (e.g. `gcp-shared-durable.tfstate`).

---

<h2 id="war-story-5" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">5. Artifact Registry vs ECR: Different Image Paths and Auth</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Artifact Registry, ECR, GCP, AWS, container registry, docker push
**difficulty:** 6
**significance:** 8

<h3 id="war-story-5-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.1 Context</h3>

AWS ECR uses `{account_id}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}`. GCP Artifact Registry uses `{region}-docker.pkg.dev/{project_id}/{repo}/{image}:{tag}`. Auth and CLI differ.

<h3 id="war-story-5-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.2 Comparison</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Aspect</th>
<th style="padding:8px">AWS (ECR)</th>
<th style="padding:8px">GCP (Artifact Registry)</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>URL format</strong></td>
<td style="padding:8px;background:#e8f5e9"><code>123456789.dkr.ecr.us-east-1.amazonaws.com/fru-app:latest</code></td>
<td style="padding:8px;background:#e8f5e9"><code>us-central1-docker.pkg.dev/my-proj/fru-app-repo/app:latest</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Auth</strong></td>
<td style="padding:8px;background:#fff3e0"><code>aws ecr get-login-password</code> → <code>docker login</code></td>
<td style="padding:8px;background:#fff3e0"><code>gcloud auth configure-docker {region}-docker.pkg.dev</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Create repo</strong></td>
<td style="padding:8px;background:#e8f5e9"><code>aws ecr create-repository</code></td>
<td style="padding:8px;background:#e8f5e9"><code>gcloud artifacts repositories create</code> (or Terraform)</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Terraform</strong></td>
<td style="padding:8px;background:#fff3e0"><code>aws_ecr_repository</code></td>
<td style="padding:8px;background:#fff3e0"><code>google_artifact_registry_repository</code></td>
</tr>
</tbody>
</table>

<h3 id="war-story-5-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.3 Key Insight</h3>

> `build_and_push_images.py` for GCP must use `gcloud artifacts docker` or `docker push` with Artifact Registry URL. Do not reuse ECR URLs or `aws ecr get-login-password`. The image path structure is different; ensure `artifact_registry_repo_app` and `artifact_registry_repo_spark` resolve to the correct `{region}-docker.pkg.dev/{project}/{repo}/...` format.

<h3 id="war-story-5-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">5.4 Takeaway</h3>

(1) Enable **Artifact Registry API** in GCP Console before first deploy. (2) `gcloud auth configure-docker {region}-docker.pkg.dev` for local dev. (3) In CI/GKE, use Workload Identity or service account; no `docker login` needed when pushing from GKE. (4) Reference: `tools/gcp/scope_shared/deploy/build_and_push_images.py`.

---

<h2 id="war-story-6" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">6. GCP Required APIs: Enable Before First Deploy</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** GCP, APIs, enable, Cloud Storage, Cloud SQL, GKE, Artifact Registry
**difficulty:** 4
**significance:** 7

<h3 id="war-story-6-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.1 Context</h3>

GCP requires specific APIs to be enabled per project. Unlike AWS (where most services work once IAM is configured), GCP APIs are opt-in. If an API is not enabled, Terraform or CLI calls fail with cryptic errors like "API not enabled" or "Permission denied."

<h3 id="war-story-6-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.2 Required APIs (for this project)</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">API</th>
<th style="padding:8px">Purpose</th>
<th style="padding:8px">Notes</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Cloud Storage API</strong></td>
<td style="padding:8px;background:#e8f5e9">GCS buckets, state</td>
<td style="padding:8px;background:#e8f5e9">Use "Cloud Storage API" (not just "Cloud Storage")</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Cloud SQL Admin API</strong></td>
<td style="padding:8px;background:#fff3e0">Cloud SQL</td>
<td style="padding:8px;background:#fff3e0"><strong>Needs to be enabled</strong></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Kubernetes Engine API</strong></td>
<td style="padding:8px;background:#e8f5e9">GKE</td>
<td style="padding:8px;background:#e8f5e9"><strong>Needs to be enabled</strong>; propagation can take minutes</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Artifact Registry API</strong></td>
<td style="padding:8px;background:#fff3e0">Container images</td>
<td style="padding:8px;background:#fff3e0"><strong>Needs to be enabled</strong> for pushing Docker images</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Secret Manager API</strong></td>
<td style="padding:8px;background:#e8f5e9">Secrets</td>
<td style="padding:8px;background:#e8f5e9">For durable_with_cooloff</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Serverless VPC Access API</strong></td>
<td style="padding:8px;background:#fff3e0">VPC connector</td>
<td style="padding:8px;background:#fff3e0">For Cloud Run → Cloud SQL</td>
</tr>
</tbody>
</table>

<h3 id="war-story-6-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.3 Key Insight</h3>

> Enable APIs in **APIs & Services → Library** before running Terraform. `doctor.py` can check for common APIs; document the full list in `REFACTOR_PLAN_GCP_READINESS.md`. If a deploy fails with "API not enabled" or 403, enable the missing API and retry.

<h3 id="war-story-6-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">6.4 Takeaway</h3>

(1) Create a checklist in `doctor.py` or `docs/` for required APIs. (2) Kubernetes Engine API enablement can take a few minutes to propagate. (3) Service account must have roles that allow use of these APIs (e.g. `roles/run.admin`, `roles/sql.admin`).

---

<h2 id="war-story-7" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">7. GCP State Bucket Naming: project_id vs account_id</h2>

**creation:** `<260227>`
**last_updated:** `<260227>`

**keywords:** Terraform, state bucket, GCP, AWS, naming, project_id, account_id
**difficulty:** 5
**significance:** 6

<h3 id="war-story-7-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.1 Context</h3>

AWS state bucket uses `{prefix}-{component}-{env}-{region}-{account_id}`. GCP uses `{prefix}-{component}-{env}-{region}-{project_id}`. The last identifier differs: AWS uses the 12-digit account ID; GCP uses the project ID string.

<h3 id="war-story-7-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.2 Comparison</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Cloud</th>
<th style="padding:8px">Identifier</th>
<th style="padding:8px">Example</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>AWS</strong></td>
<td style="padding:8px;background:#e8f5e9"><code>get_account_id()</code> via <code>aws sts get-caller-identity</code></td>
<td style="padding:8px;background:#e8f5e9"><code>fru-tf-state-dev-us-east-1-123456789012</code></td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>GCP</strong></td>
<td style="padding:8px;background:#fff3e0"><code>GCP_PROJECT_ID</code> from env</td>
<td style="padding:8px;background:#fff3e0"><code>fru-tf-state-dev-us-central1-my-gcp-project</code></td>
</tr>
</tbody>
</table>

<h3 id="war-story-7-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.3 Key Insight</h3>

> `resolve_state_bucket()` in `tools/gcp/scope_shared/core/backend.py` must use `GCP_PROJECT_ID`, not `get_account_id()`. GCP has no `sts get-caller-identity` equivalent; project ID is the canonical identifier. Ensure `GCP_PROJECT_ID` is set in `.env` before deploy.

<h3 id="war-story-7-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">7.4 Takeaway</h3>

(1) `tools/aws/backend.py` calls `get_account_id()`; `tools/gcp/backend.py` uses `os.getenv("GCP_PROJECT_ID")`. (2) Do not try to derive project ID from gcloud config in tools—use env var for consistency with Terraform and CI. (3) `doctor.py` should verify `GCP_PROJECT_ID` is set.

---

<h2 id="war-story-8" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">8. Service Networking Peering Teardown: Compute API vs Service Networking API</h2>

**creation:** `<260305>`
**last_updated:** `<260305>`

**keywords:** GCP, service networking, VPC peering, Cloud SQL, teardown, Producer services still using, Compute API, durable pre-destroy
**difficulty:** 8
**significance:** 9

<h3 id="war-story-8-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.1 Context</h3>

When tearing down the GCP durable stack (VPC + Cloud SQL + Private Service Access), the conventional approach is: (1) destroy Cloud SQL first, (2) wait for it to be gone, (3) destroy the service networking connection (`google_service_networking_connection.default`). Terraform and `gcloud services vpc-peerings delete` both use the **Service Networking API**. After Cloud SQL is deleted, that API enforces a check that no producer services (Cloud SQL, Memorystore, etc.) are still using the connection. GCP's backend releases the connection asynchronously—often taking **10–30+ minutes**, and in our case **40+ minutes** with no success.

<h3 id="war-story-8-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.2 The Problem: "Producer services still using"</h3>

Using the conventional commands:

- `tofu destroy -target=google_service_networking_connection.default`
- `gcloud services vpc-peerings delete --network=fru-dev-net`

Both fail repeatedly with:

```text
Error: Unable to remove Service Networking Connection, err: Error waiting for Delete Service Networking Connection: 
Error code 9, message: Failed to delete connection; Producer services (e.g. CloudSQL, Cloud Memstore, etc.) 
are still using this connection.
```

We polled for **40+ minutes**—Cloud SQL was long gone (`gcloud sql instances list` showed 0), but the Service Networking API kept rejecting the delete. GCP does not expose a status to poll; the only "verification" is retrying the delete until it succeeds. Community reports (Terraform provider issue #19908) describe the same issue lasting **days** in some cases.

<h3 id="war-story-8-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.3 The Breakthrough: Console UI Delete Works Instantly</h3>

In the GCP Console, we navigated to **VPC network → VPC network peering**, selected `servicenetworking-googleapis-com`, and clicked **Delete**. The peering was removed **instantly**—no "Producer services still using" error. The same peering that the Service Networking API refused to delete for 40+ minutes was gone in seconds via the UI.

**Why?** The Console's VPC network peering page uses the **Compute Engine API** (`networks.removePeering`), not the Service Networking API. The Compute API removes the peering from the consumer's network side and does **not** enforce the "Producer services still using" check. Both APIs operate on the same underlying peering; they simply take different deletion paths.

<h3 id="war-story-8-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.4 The Solution: gcloud compute + tofu state rm</h3>

We adopted the equivalent of the Console delete:

1. **`gcloud compute networks peerings delete servicenetworking-googleapis-com --network=fru-dev-net --project=...`** — Uses Compute API; succeeds immediately (or reports "there is no peering" if already gone).
2. **`tofu state rm google_service_networking_connection.default`** — Removes the resource from Terraform state so the subsequent full durable destroy does not attempt a Service Networking API delete (which would fail or block).

This "strange combo" is necessary because: (a) Terraform manages the connection via the Service Networking API, which blocks; (b) the Compute API bypasses that block; (c) after deleting via Compute API, the resource is gone in GCP but still in Terraform state—we must `state rm` to keep state in sync.

<h3 id="war-story-8-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.5 Workflow Diagram</h3>

```mermaid
%%{init: {'themeVariables': {'fontSize': '8px', 'fontFamily': 'arial'}}}%%
flowchart TB
    subgraph CONV["❌ Conventional (Service Networking API)"]
        direction TB
        A1["tofu destroy -target=module.cloud_sql"] --> A2["Poll: gcloud sql describe until 404"]
        A2 --> A3["tofu destroy -target=google_service_networking_connection"]
        A3 -->|"40+ min: Producer services still using"| A4["⏳ Blocked"]
    end

    subgraph SOL["✅ Our approach (Compute API)"]
        direction TB
        B1["tofu destroy -target=module.cloud_sql"] --> B2["Poll: gcloud sql describe until 404"]
        B2 --> B3["gcloud compute networks peerings delete"]
        B3 -->|"Instant (or 'no peering')"| B4["tofu state rm connection"]
        B4 --> B5["Full durable destroy"]
    end

    subgraph INSP["💡 Inspiration"]
        C1["Console UI: VPC peering → Delete"]
        C2["Works instantly"]
        C1 --> C2
    end

    style CONV fill:#ffcccc,font-size:9px
    style SOL fill:#ccffcc,font-size:9px
    style INSP fill:#ffffcc,font-size:9px
    style A4 fill:#ff9999,font-size:9px
```

<h3 id="war-story-8-sec-6" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.6 Key Insight</h3>

> Two deletion paths exist for the same service networking peering: (1) **Service Networking API** (tofu, `gcloud services vpc-peerings delete`) — enforces "Producer services still using" and can block for 40+ min or days. (2) **Compute API** (`gcloud compute networks peerings delete`, Console UI) — removes peering from consumer network, succeeds immediately. Use the Compute API path in pre-destroy, then `tofu state rm` to sync state.

<h3 id="war-story-8-sec-7" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">8.7 Takeaway</h3>

(1) Pre-destroy in `durable_pre_destroy.py` uses `gcloud compute networks peerings delete` instead of tofu targeted destroy. (2) Treat "there is no peering" / "not found" as success (idempotent when peering already deleted manually). (3) Always run `tofu state rm google_service_networking_connection.default` after deleting via gcloud so full destroy doesn't attempt Service Networking API delete. (4) Reference: `tools/gcp/scope_shared/teardown/durable_pre_destroy.py` and Terraform provider issue [#19908](https://github.com/hashicorp/terraform-provider-google/issues/19908).

---

<h2 id="war-story-9" style="color:#1565c0;margin-top:1.35em;margin-bottom:0.5em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px">9. Smart DB Loading Strategy: Verify-Only Fallback Instead of Fail-Fast</h2>

**creation:** 260312  
**last_updated:** 260312  

**keywords:** Cloud Run Job, db-setup, schema + load, verify-only, fail-fast, recovery path, idempotent deploy  
**difficulty:** 5  
**significance:** 7  

<h3 id="war-story-9-sec-1" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.1 Context</h3>

On GCP, database setup (schema + CSV load + OpenAI embeddings into `fru_sales_embeddings`) runs inside a **Cloud Run Job** (private-IP Cloud SQL). The job can fail for many reasons: timeout (e.g. 900s poll limit), missing env in the container (e.g. `OPENAI_EMBED_MODEL`), transient API errors, or image/config bugs. If we **fail-fast** on the first exception, we abort the entire deploy. That is correct when the DB is genuinely broken or never initialized—but it is wasteful when the failure is transient or late (e.g. job timed out *after* successfully loading data, or a previous deploy already populated the DB).

<h3 id="war-story-9-sec-2" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.2 The Tension</h3>

General orchestration wisdom (see WAR_STORIES_CLOUD_SHARED) says: *check exit codes, exit 1 on failure, do not report success when a critical step failed.* So one might expect: “schema job failed → exit 1 immediately.” The nuance here is that “schema job failed” does not always mean “DB is unusable.” The job is **asynchronous** and **long-running**; we only observe success or failure after the fact. A timeout or a late exception (e.g. after schema and CSV load but during embeddings) can leave the DB in a good state. Failing the deploy then forces a full rerun or manual intervention even when a cheap check would show the DB is already OK.

<h3 id="war-story-9-sec-3" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.3 Smart Strategy: Verify-Only Fallback</h3>

We intentionally **do not** abort on the first exception. When the full schema+load job fails:

1. **Log the failure** (we do not hide it).
2. **Run a verify-only job**: a separate, lightweight Cloud Run Job execution with `FRU_VERIFY_ONLY=true` that only connects to the DB and runs `SELECT COUNT(*) FROM fru_sales_embeddings`, then emits `FRU_EMBEDDINGS_COUNT=N` for parsing.
3. **If the count matches the expected value** (e.g. 200 rows from the reference CSV), treat the DB as already initialized and **continue the deploy**.
4. **If the count is wrong or verify-only fails**, then re-raise and fail the deploy.

So we fail-fast on *“DB is definitely not OK”* (verify-only fails or wrong count), but we avoid failing the deploy when *“full job failed but DB is actually fine”* (e.g. timeout after load, or previous run already populated the DB).

<h3 id="war-story-9-sec-4" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.4 Justification</h3>

<table>
<thead>
<tr style="background:#1565c0;color:white">
<th style="padding:8px">Goal</th>
<th style="padding:8px">How verify-only fallback helps</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Avoid false deploy failures</strong></td>
<td style="padding:8px;background:#e8f5e9">Timeouts or late container exits after successful load would otherwise abort the deploy even though the DB has correct data.</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Idempotent / retry-friendly</strong></td>
<td style="padding:8px;background:#fff3e0">A retry or a later deploy can succeed without re-running the full heavy job if the DB was already initialized.</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Cheap recovery check</strong></td>
<td style="padding:8px;background:#e8f5e9">Verify-only is one SELECT COUNT and a short-lived container; cost and time are small compared to re-running the full schema+load+embeddings job.</td>
</tr>
<tr>
<td style="background:#e3f2fd;padding:8px"><strong>Still fail when DB is bad</strong></td>
<td style="padding:8px;background:#fff3e0">If the DB was never set up or is partial (wrong count), verify-only returns False and we raise; we do not report success when the DB is unusable.</td>
</tr>
</tbody>
</table>

This is a **recovery path**, not a way to hide errors: the first failure is always logged, and we only continue when a second, explicit check (verify-only) confirms the DB state.

<h3 id="war-story-9-sec-5" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.5 Where It Lives</h3>

- **Call site:** `tools/gcp/scope_shared/deploy/setup_database.py` — after `run_and_verify()` raises, we catch, log, then call `run_verify_only()`; on True we return successfully, otherwise we re-raise.
- **Implementation:** `tools/gcp/scope_shared/deploy/db_setup/cloud_job.py` — `run_verify_only()` creates/updates the job with `FRU_VERIFY_ONLY=true`, executes it, parses logs for `FRU_EMBEDDINGS_COUNT`, and returns True iff count matches expected.
- **Container:** Same db-setup image; `run_schema_and_load.py` branches on `FRU_VERIFY_ONLY` to skip schema/load and only run the count query.

<h3 id="war-story-9-sec-6" style="color:#00695c;margin-top:1.05em;margin-bottom:0.4em;font-weight:600">9.6 Takeaway</h3>

(1) For long-running, async jobs that mutate shared state (e.g. DB), consider a **lightweight verification step** when the job “fails”—so you can distinguish “state is bad” from “job failed but state may still be good” (e.g. timeout after success). (2) Document this as a deliberate **recovery path** so future maintainers do not “fix” it by making the flow fail-fast and remove verify-only. (3) Keep the first failure visible in logs; only continue when the verification step explicitly confirms the desired state. (4) Reference: `tools/gcp/scope_shared/deploy/db_setup/cloud_job.py` (`run_verify_only` docstring) and `setup_database.py` (catch + verify-only blocks).

---
