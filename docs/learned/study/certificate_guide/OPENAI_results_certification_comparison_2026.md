# Cloud AI / Agent AI / MLOps Certification Comparison (March 2026)

> **Tables:** Styled per [docs/styles/DOCS_TABLE_STYLE.md](../../../styles/DOCS_TABLE_STYLE.md) — compact HTML, badges, alternating rows.

This note consolidates four comparison areas:

1. **General cloud AI / ML engineer** certifications  
2. **Agent AI / Generative AI** certifications (vendor proctored)  
3. **MLOps / production ML** certifications  
4. **Senior / architect-level** AI & cloud solution design credentials  

---

## Legend (readability)

**Popularity** is an informed proxy (vendors rarely publish exam volume). Based on platform adoption, hiring visibility, and ecosystem breadth.

| Badge | Meaning |
|-------|---------|
| <span style="background:#c8e6c9;padding:2px 6px">High</span> | Strong / recommended / broad recognition |
| <span style="background:#fff9c4;padding:2px 6px">Med</span> | Moderate / situational |
| <span style="background:#fff3e0;padding:2px 6px">M–H</span> | Medium–high effort or depth |
| <span style="background:#ffcdd2;padding:2px 6px">Hard</span> | High difficulty |
| <span style="background:#e3f2fd;padding:2px 6px">Deep</span> | Especially technical / lifecycle depth |
| <span style="background:#2e7d32;color:white;padding:1px 6px">FRU+</span> | Strong fit for FRU GenAI Analytics delivery |

**FRU column (tables §1–§4):** Concrete ways to align the **`fru-genai-analytics-new`** repo (AWS-first GenAI analytics platform, IaC, docs) with each cert—for **exam study anchors** and **interview/portfolio** storytelling. Badges (e.g. FRU+) summarize fit; cells spell out what to build or document.

---

## 1) General cloud AI / ML engineer

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:9%;">Provider</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:17%;">Certification</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:19%;">Focus <small>(compact)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:11%;">Depth • Diff • Prep</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:30%;">FRU <small>(fru-genai-analytics-new)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:14%;">Pop.</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>GCP</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Professional ML Engineer<br><small><a href="https://cloud.google.com/learn/certification/machine-learning-engineer">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">End-to-end ML • Vertex • MLOps • GenAI</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span><br><small>8–16 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">Strong</span><br>Grow <code>infra_terraform/live_deploy/gcp/</code> + docs into a <b>Vertex-shaped story</b>: data → training → registry → batch/online serving • monitoring &amp; retraining for analytics models. Portfolio: 1–2 diagrams + narrative mapping FRU components to PMLE domains (pipelines, serving, GenAI on Vertex).</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>AWS</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">ML Engineer – Associate (MLA-C01)<br><small><a href="https://aws.amazon.com/certification/certified-machine-learning-engineer-associate/">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Data → deploy • orchestration • monitor • security</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">M–H</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span><br><small>6–14 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Repo is already <b>AWS-first</b> (EKS/ECS, <code>tools/aws/deploy.py</code>, Terraform). For MLA: document/implement <b>SageMaker-parallel</b> flows—pipelines or clear equivalent, model registry, endpoint patterns, drift/alarms, IAM/VPC for inference. Interview: walk “ingest → train → deploy → monitor” using FRU as the system you own.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Oracle</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">OCI 2025 GenAI Pro (1Z0-1127-25)<br><small><a href="https://education.oracle.com/oracle-cloud-infrastructure-2025-generative-ai-professional/pexam_1Z0-1127-25">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">OCI GenAI • embed • RAG agents</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 3px">Med</span><br><span style="background:#fff9c4;padding:1px 3px">Med</span><br><small>1–6 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>FRU’s default stack isn’t OCI—use a <b>parallel design doc</b> (or tiny sandbox) that replays the <i>same analytics GenAI use case</i> with OCI GenAI, embeddings, RAG agents. Exam prep: map each FRU pattern (retrieve → generate → ground) to OCI services; portfolio shows cross-cloud fluency.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Niche</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Azure</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">AI Engineer Associate (AI-102)<br><small><a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/">cert page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Azure AI • OpenAI • search • GenAI • agents</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 3px">M–H</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span><br><small>6–10 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Add an <b>Azure lane</b> in IaC/docs: Azure OpenAI, AI Search (or Foundry) mirroring FRU retrieval &amp; agents • private endpoints, managed identity, logging. Same product story on Azure = strong AI-102 interview demo (“I shipped FRU on AWS; here’s the enterprise Azure twin”).</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
</tbody>
</table>

**Takeaways:** <span style="background:#c8e6c9;padding:1px 4px">✓</span> Long-term engineering signal: **AWS MLA-C01** • Deepest ML eng.: **GCP PMLE** • Fastest GenAI ROI: **Oracle OCI** • Enterprise integration: **Azure AI-102**

**Pragmatic order (FRU + production):** ① AWS MLA-C01 → ② Azure AI-102 *or* Oracle OCI (stack) → ③ GCP PMLE (optional depth)

---

## 2) Agent AI / GenAI (official proctored only)

> <span style="background:#ffcdd2;padding:2px 4px">⚠</span> DeepLearning.AI = course certificates, not vendor-style proctored exams — **excluded** from this table.

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:8%;">Provider</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:22%;">Certification</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:8%;">Level</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:20%;">Focus</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:32%;">FRU <small>(fru-genai-analytics-new)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:10%;">Pop.</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>AWS</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Generative AI Developer – Professional<br><small><a href="https://aws.amazon.com/certification/certified-generative-ai-developer-professional/">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Prof.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">FM integration • Bedrock • prod GenAI • governance</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Ground FRU’s LLM features in <b>Bedrock</b> (model choice, KB/RAG, Agents/tooling where fit) • add explicit <b>governance</b> notes: guardrails, eval harness, prompt/version policy, logging, cost guardrails. Portfolio: “before/after” architecture—custom vs Bedrock—and how you’d test &amp; ship safely (maps to exam’s prod + optimization domains).</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Azure</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">AI Engineer (AI-102)<br><small><a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/">cert</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Assoc.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">OpenAI • search • GenAI • agents • extraction</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Same as §1 Azure row, tuned to <b>agents + search + extraction</b>: implement or document Azure OpenAI + AI Search (chunking, skillsets/indexers) + optional Foundry agent flows that mirror FRU’s analytics Q&amp;A. Rehearse “design interview” using FRU domain (metrics, reports) as the workload.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Oracle</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">OCI 2025 GenAI Pro<br><small><a href="https://education.oracle.com/oracle-cloud-infrastructure-2025-generative-ai-professional/pexam_1Z0-1127-25">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Assoc.+</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">OCI GenAI • RAG agents • LLM workflows</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Repeat the <b>same RAG/agent user journeys</b> as FRU but label each step with OCI GenAI + RAG Agents services; optional hands-on lab. Exam: memorize service boundaries &amp; integration points; job: show you can port an AWS-style analytics assistant design to Oracle when the customer mandates OCI.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Niche</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>GCP</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Generative AI Leader<br><small><a href="https://cloud.google.com/learn/certification/generative-ai-leader">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Business</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">GenAI fundamentals • GCP offerings • strategy</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span><br>Less code-heavy—use FRU as the <b>case study</b> in a short exec brief: which GCP GenAI/Vertex capabilities you’d use, risks, responsible AI, KPIs. Good for “strategy + portfolio” interviews; pair with PMLE/PCA if you need deeper hands-on proof.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>AWS</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">AI Practitioner (AIF-C01)<br><small><a href="https://aws.amazon.com/certification/certified-ai-practitioner/">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Found.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">AI/GenAI basics • AWS AI • Bedrock awareness</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span><br>Annotate one <b>FRU architecture diagram</b> with practitioner-level labels: when to use Bedrock vs bespoke, data privacy, responsible AI, cost. Use FRU as your single flashcard “system” while reading the exam guide—fast vocabulary alignment without new scope.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span></td>
</tr>
</tbody>
</table>

**Takeaways:** Most **engineering** agent/GenAI cert: **AWS GenAI Developer – Prof.** • **Enterprise** GenAI/agents: **Azure AI-102** • **Fast** RAG/embeddings: **Oracle OCI**

**Sequence (RAG + tools + prod apps):** ① AWS GenAI Developer – Prof. → ② Azure AI-102 → ③ Oracle OCI GenAI Pro

---

## 3) MLOps / production ML

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:8%;">Provider</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:17%;">Certification</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:19%;">Focus</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:9%;">Depth • Diff</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:6%;">Prep</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:31%;">FRU <small>(fru-genai-analytics-new)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:10%;">Pop.</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>AWS</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">ML Engineer – Assoc. (MLA-C01)<br><small><a href="https://aws.amazon.com/certification/certified-machine-learning-engineer-associate/">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Data prep • modeling • deploy • orchestrate • monitor</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">M–H</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><small>6–14 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Same as §1 AWS: treat FRU as the <b>MLOps reference system</b>—add/runbooks for pipeline steps, model promotion, observability (CloudWatch/X-Ray or equivalent), security in VPC. For interviews, narrate incident response &amp; retrain loop on the analytics models behind FRU.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>GCP</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Professional ML Engineer<br><small><a href="https://cloud.google.com/learn/certification/machine-learning-engineer">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Full lifecycle • pipelines • serving • monitor • Vertex GenAI</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><small>8–16 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span><br>Emphasize <b>automated pipelines</b>, experiment tracking, batch vs online prediction, and GenAI ops (Vertex) in docs—either on GCP or as a target-state diagram from AWS. Show how FRU’s analytics models move from notebook to governed production (PMLE loves lifecycle breadth).</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Azure</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">AI Engineer (AI-102)<br><small><a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/">cert</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">AI lifecycle • integration • monitor • GenAI • search • agents</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 3px">M–H</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><small>6–10 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span><br>Frame FRU’s <b>operational story</b> on Azure: monitoring App Insights/Log Analytics for AI APIs, CI/CD for model/config changes, content safety. Not “pure MLOps,” but strong if you document end-to-end AI solution lifecycle for the analytics product.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Databricks</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">ML Professional<br><small><a href="https://www.databricks.com/learn/certification/machine-learning-professional">exam</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Lakehouse ML • MLflow • features • deploy • monitoring</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 3px">High</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><small>4–10 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">FRU+</span><br>Add a <b>lakehouse layer</b> to FRU’s story: curated analytics tables → feature sets → MLflow experiments → scheduled scoring jobs • monitoring &amp; rollback. Even if compute stays on AWS, a crisp “Databricks-shaped” design doc proves platform ML maturity to hiring managers.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">M–H</span></td>
</tr>
</tbody>
</table>

**Takeaways:** **MLOps balance:** AWS MLA-C01 • **Deepest** lifecycle: GCP PMLE • **Lakehouse-centric:** Databricks • AI-102 = broader AI eng., not pure MLOps

**Sequence (pipelines + LLM/ML + monitoring):** ① AWS MLA-C01 → ② Databricks ML Pro → ③ GCP PMLE

---

## 4) Senior / architect-level AI & cloud certifications

> **Scope:** These credentials stress **end-to-end solution design**—requirements, trade-offs, security, cost, multi-service patterns, and stakeholder alignment—often with **experience expectations** and **prerequisites** (e.g. associate-level exams). They **complement** §1–§3 (implementation depth); they are **not** a substitute for hands-on ML/GenAI engineering badges unless your role is explicitly architecture-led.  
> **Research basis (Mar 2026):** Vendor exam guides / cert catalogs ([AWS SAP-C02](https://aws.amazon.com/certification/certified-solutions-architect-professional/), [Azure AZ-305](https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/), [Agentic AI Architect](https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/), [GCP Professional Cloud Architect](https://cloud.google.com/learn/certification/cloud-architect), [Oracle 1Z0-997-25](https://education.oracle.com/oracle-cloud-infrastructure-2025-architect-professional/pexam_1Z0-997-25)); confirm current exam IDs and retirement dates on each provider’s site.

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:8%;">Provider</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:17%;">Certification</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:18%;">Focus <small>(vs §1–3)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:10%;">Architect signal</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:11%;">Depth • Diff • Prep</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:28%;">FRU <small>(fru-genai-analytics-new)</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:8%;">Pop.</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>AWS</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Solutions Architect – Professional (SAP-C02)<br><small><a href="https://aws.amazon.com/certification/certified-solutions-architect-professional/">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Multi-account • hybrid • migration • cost • security • <b>where AI/ML fits</b> in platform patterns (not a dedicated “AI architect” exam)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">Cloud arch.</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span><br><small>8–20 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span> <small>governance</small><br>Produce a <b>Well-Architected–style review</b> of FRU’s AWS footprint: multi-account/OUs, VPC segmentation for EKS/ECS + data stores, KMS/secrets, backup/DR, cost allocation for inference/training. Practice SAP-C02 scenarios by redesigning FRU for scale, compliance, and hybrid edge cases—talk track for staff/principal interviews.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Azure</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Solutions Architect Expert <small>(AZ-305)</small><br><small><a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/">cert page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Identity • networking • data • governance • BCDR • landing zones • <b>hosting AI services</b> at enterprise scale</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">Cloud arch.</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span><br><small>8–18 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span> <small>platform</small><br>Draft a <b>parallel Azure landing zone</b> that hosts the same analytics GenAI workload: subscriptions, hub/spoke networking, Private Link to OpenAI/Search, Entra ID patterns, policy/guardrails. Use FRU’s AWS diagram as the source of truth so AZ-305 study = “translate FRU to Azure enterprise patterns,” not greenfield trivia.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">V.High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Azure</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Agentic AI Business Solutions Architect <small>(AB-100)</small><br><small><a href="https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/">cert page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>AI-first architecture</b> • agentic / multi-agent • Copilot Studio / Power / Dynamics / Foundry • security • value case <small>(prereqs include AI-102 or listed associates—see Learn)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">AI arch.</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#fff3e0;padding:1px 3px">M–H</span><br><small>6–14 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span> <small>MS stack</small><br>Map FRU’s agents/RAG to <b>Microsoft business stack</b> story: Copilot Studio / Power Platform / Dynamics + Foundry for the same analytics outcomes—security, multi-agent handoffs, human-in-the-loop, ROI. If FRU stays AWS-hosted, write a “<b>Microsoft twin</b>” solution outline for AB-100 case-style answers and to show enterprise agentic architecture literacy.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span> <small>niche</small></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>GCP</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Professional Cloud Architect<br><small><a href="https://cloud.google.com/learn/certification/cloud-architect">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Reliability • security • cost • operations • case-style design • <b>Vertex / data/ML</b> as part of solution fabric</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">Cloud arch.</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span><br><small>8–18 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span> <small>platform</small><br>Redo FRU as <b>PCA case studies</b>: reliability (MIG, multi-region), security (VPC-SC, IAM, CMEK), cost (preemptible/batch training, committed use), ops (logging, SLOs). Place Vertex + data services on diagrams the way the exam expects—practice 45–60 min “design this analytics platform on GCP” using FRU as the requirements brief.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">High</span></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Oracle</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">OCI 2025 Architect Professional <small>(1Z0-997-25)</small><br><small><a href="https://education.oracle.com/oracle-cloud-infrastructure-2025-architect-professional/pexam_1Z0-997-25">exam page</a></small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">HA • DR • tenancy • networking • data platform choices • <b>placement of GenAI/ML services</b> on OCI</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#c8e6c9;padding:1px 4px">Cloud arch.</span></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#e3f2fd;padding:1px 3px">Deep</span><br><span style="background:#ffcdd2;padding:1px 3px">Hard</span><br><small>8–16 wk</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Med</span> <small>OCI shops</small><br>Produce an <b>OCI reference architecture</b> for FRU’s analytics + GenAI tier: compartments, VCNs, HA/DR, data services placement, integration with OCI GenAI. High value if you sell to Oracle customers; otherwise use as scenario practice and “second cloud” proof for architects.</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:1px 4px">Niche</span></td>
</tr>
</tbody>
</table>

> **GCP nuance:** **Professional ML Engineer** (§1 / §3) is often the **stronger technical depth** signal for ML systems; **Professional Cloud Architect** is the broader **enterprise solution-design** credential—many senior profiles hold **both** or pair PCA with PMLE.  
> **Databricks:** No separate proctored **“AI solutions architect”** exam; senior practice is usually **Databricks ML Professional** (§3) plus **cloud architect** skills on AWS/GCP/Azure.  
> **Microsoft detail:** For agentic / Foundry-heavy delivery, see also [AI-102 vs AI-200 vs Agentic Architect](microsoft_ai_ai102_ai200_agentic_architect_comparison.md) on this site.

**Takeaways:** Broad **hyperscaler architect** signal: **AWS SAP-C02**, **Azure Solutions Architect Expert**, **GCP PCA**, **OCI Architect Pro** (stack-dependent). **Microsoft-specific AI solution architecture:** **Agentic AI Business Solutions Architect (AB-100)**.

**Typical stack order (architecture-led):** ① Implementation cert in your cloud (§1–3) → ② **Solutions Architect Pro / PCA / OCI Arch Pro** → ③ **AB-100** if the estate is Microsoft agentic / Power / Dynamics-heavy

---

## Executive summary

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:42%;">Objective</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:58%;">Best pick</th>
</tr>
</thead>
<tbody>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>All-round cloud ML engineering</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;">AWS MLA-C01</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Deepest ML + MLOps</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;">GCP Professional ML Engineer</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Fast GenAI implementation</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;">Oracle OCI GenAI Professional</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Enterprise AI / GenAI integration</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;">Azure AI Engineer (AI-102)</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Agent AI engineering (current)</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;">AWS GenAI Developer – Professional</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Lakehouse MLOps</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;">Databricks ML Professional</td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Senior cloud architect (AI-heavy workloads)</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;">AWS SAP-C02 <small>or</small> GCP PCA <small>or</small> Azure AZ-305 <small>or</small> OCI Arch Pro — <i>by primary cloud</i></td></tr>
<tr><td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;"><b>Microsoft agentic / business AI architecture</b></td><td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;">Agentic AI Business Solutions Architect (AB-100)</td></tr>
</tbody>
</table>

### Suggested paths <small>(numbered)</small>

| Path | Order |
|------|--------|
| **A — Fast FRU value** | ① Oracle OCI GenAI Pro • ② AWS MLA-C01 • ③ Azure AI-102 |
| **B — Long-term cloud AI engineer** | ① AWS MLA-C01 • ② GCP PMLE • ③ Azure AI-102 |
| **C — Agent AI + MLOps** | ① AWS GenAI Developer – Prof. • ② AWS MLA-C01 • ③ Databricks ML Pro |
| **D — Architecture / platform** | ① Core implementation cert in target cloud (§1–3) • ② AWS SAP-C02 / Azure AZ-305 / GCP PCA / OCI 1Z0-997-25 • ③ AB-100 if Microsoft agentic estate |

---

## Research notes / sources

**Official pages:** GCP PMLE, GenAI Leader & **Professional Cloud Architect** • AWS MLA-C01, GenAI Developer – Prof., AI Practitioner & **Solutions Architect – Professional** • [Azure AI-102](https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/), **[Azure Solutions Architect Expert](https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/)**, **[Agentic AI Business Solutions Architect](https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/)** • Oracle 1Z0-1127-25 & **1Z0-997-25** • Databricks ML Professional — URLs as linked in tables above.

**Popularity proxies (illustrative):** cloud market reporting (e.g. CRN, TechTarget), Stack Overflow survey, AWS ecosystem commentary, Databricks revenue reporting (Reuters)—same intent as original note; verify independently for decisions.
