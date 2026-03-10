## Unit Test Strategy (Project-Specific)

This document summarizes **where to focus unit tests in this repo** and how to structure them by type and priority, using the same table style as our other docs.

---

## 1. What to test first in this repo

### 1.1. Core areas and priorities

<table>
<tr style="background:#1565c0;color:white">
<th>Area</th>
<th>Key modules / entrypoints</th>
<th>What to test</th>
<th>Priority</th>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>① API layer</strong></td>
<td style="background:#e8f5e9">• <code>core_app/backend/api/app.py</code><br>• FastAPI routers (REST + SSE)</td>
<td style="background:#e8f5e9">• Health/ready endpoints<br>• Main analytics/query endpoints (happy path + 4xx/5xx)<br>• SSE streaming behavior (small, deterministic streams)</td>
<td style="background:#e8f5e9"><span style="background:#2e7d32;color:white;padding:1px 4px;font-size:0.85em">top</span></td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>② Agents & tools</strong></td>
<td style="background:#fff3e0">• <code>core_app/backend/agents/tools/*.py</code><br>• e.g. <code>semantic_search_tool.py</code></td>
<td style="background:#fff3e0">• Input validation / normalization<br>• Mapping request → search query → response object<br>• Error handling when backends fail</td>
<td style="background:#fff3e0"><span style="background:#c8e6c9;padding:2px 4px">high</span></td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>③ Verify tools</strong></td>
<td style="background:#e8f5e9">• <code>tools/cloud_shared/verify/verify_api_endpoints.py</code><br>• <code>tools/cloud_shared/verify/verify_sse.py</code><br>• <code>tools/local/standalone/doctor.py</code></td>
<td style="background:#e8f5e9">• Endpoint selection + URL building<br>• Interpretation of HTTP/SSE responses<br>• Timeouts / retry behavior</td>
<td style="background:#e8f5e9"><span style="background:#c8e6c9;padding:2px 4px">high</span></td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>④ Deploy / infra helpers</strong></td>
<td style="background:#fff3e0">• <code>tools/*/deploy_*.py</code><br>• <code>tools/*/kube_apply.py</code><br>• <code>tools/local/start_local.py</code></td>
<td style="background:#fff3e0">• Command construction for <code>tofu</code>, <code>kubectl</code>, <code>docker-compose</code><br>• Config parsing (e.g. <code>local_deploy_config.yaml</code>)</td>
<td style="background:#fff3e0"><span style="background:#fff9c4;padding:2px 4px">medium</span></td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>⑤ Utilities / helpers</strong></td>
<td style="background:#ffebee">• Logging / small helpers<br>• Formatting utilities</td>
<td style="background:#ffebee">• Only non-trivial logic<br>• Edge cases that have bitten you before</td>
<td style="background:#ffebee"><span style="background:#c8e6c9;padding:2px 4px">low</span></td>
</tr>
</table>

---

## 2. Test types and coverage targets

### 2.1. Unit test vs integration test focus

<table>
<tr style="background:#1565c0;color:white">
<th>Aspect</th>
<th style="background:#2e7d32;color:white">Unit tests (fast)</th>
<th style="background:#6a1b9a;color:white">Integration / API tests</th>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>① Scope</strong></td>
<td style="background:#e8f5e9">• Single module / function<br>• Business logic without network/DB</td>
<td style="background:#f3e5f5">• API surface (REST/SSE)<br>• Verify tools talking to running stack</td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>② Dependencies</strong></td>
<td style="background:#e8f5e9">• Heavy use of mocks/fakes for DB, HTTP, queues<br>• No real cloud calls</td>
<td style="background:#f3e5f5">• Real HTTP to dev/staging endpoints<br>• Real cloud resources (or ephemeral env)</td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>③ When to run</strong></td>
<td style="background:#e8f5e9">• Every PR and local run<br>• As part of pre-commit hooks (optional)</td>
<td style="background:#f3e5f5">• On <code>main</code> merges and nightly<br>• Before promoting to staging/prod</td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>④ Coverage goal</strong></td>
<td style="background:#e8f5e9">• API layer + agents: <strong>≥ 85%</strong><br>• Verify tools + deploy helpers: <strong>70–80%</strong></td>
<td style="background:#f3e5f5">• Focus on critical flows, not %<br>• Health checks, core analytics flows, SSE streaming</td>
</tr>
<tr>
<td style="background:#e3f2fd"><strong>⑤ Failure impact</strong></td>
<td style="background:#e8f5e9"><span style="background:#c8e6c9;padding:2px 4px">✓</span> Block merge if red<br><span style="background:#c8e6c9;padding:2px 4px">✓</span> Fast feedback for refactors</td>
<td style="background:#f3e5f5"><span style="background:#ffcdd2;padding:2px 4px">⚠</span> Block deploy to higher envs<br>• May be allowed to occasionally fail in dev for flakiness triage</td>
</tr>
</table>

---

> For how these tests are wired into CI/CD stages (PR → dev → staging → prod), see `docs/TODO_LEARNED_CICD.md` §2.

## 4. Next concrete steps

- **Short term**
  - Add unit tests for: API routes in <code>core_app/backend/api/app.py</code>, at least one agent tool, and <code>verify_api_endpoints.py</code>.
  - Wire coverage (e.g. <code>pytest --cov</code>) into PR CI with thresholds for <code>core_app/backend</code> and <code>tools/cloud_shared/verify</code>.
- **Medium term**
  - Add integration tests that spin up the stack (local or dev env) and exercise the main analytics endpoints + SSE.
  - Ensure your CI workflows call the unit/integration suites described here (see `docs/TODO_LEARNED_CICD.md` for the end-to-end pipeline).

