# Microsoft AI credentials: AI-102 vs Exam AI-200 vs Agentic AI Business Solutions Architect

> **Purpose:** Compare **Azure AI Engineer Associate (AI-102)**, **Azure AI Cloud Developer Associate (Exam AI-200)**, and **Agentic AI Business Solutions Architect (AB-100)**.  
> **Tables:** Styled per [docs/styles/DOCS_TABLE_STYLE.md](../../../styles/DOCS_TABLE_STYLE.md) — compact HTML, badges, alternating rows (same convention as [OPENAI_results_certification_comparison_2026.md](OPENAI_results_certification_comparison_2026.md)).

**Official roadmap context:** Microsoft’s retirement/replacement matrix is summarized on [The Skills Hub Blog — *The AI job boom is here…*](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128) (Mar 2026). Dates are **planned**—confirm on [Microsoft Learn — Credentials](https://learn.microsoft.com/en-us/credentials/).

---

## Legend (badges)

| Badge | Meaning |
|-------|---------|
| <span style="background:#ffcdd2;padding:2px 6px">⚠</span> | Verify on Learn / page may lag blog / retirement risk |
| <span style="background:#c8e6c9;padding:2px 6px">✓</span> | Pro / strong fit / confirmed on Learn |
| <span style="background:#2e7d32;color:white;padding:1px 6px">recommended</span> | Preferred option for that scenario (per [DOCS_TABLE_STYLE.md](../../../styles/DOCS_TABLE_STYLE.md)) |
| <span style="background:#fff9c4;padding:2px 6px">Conceptual</span> | Useful conceptually; stack may not match repo today |
| <span style="background:#ffcdd2;padding:2px 6px">Low</span> | Weak fit unless role is explicitly that track |

---

### <span style="background:#ffcdd2;padding:2px 6px">⚠</span> Exam AI-103 vs what you can open on Learn today

Microsoft’s **blog** names **Exam AI-103** and **Microsoft Certified: Azure AI App and Agent Developer Associate** as the replacement for **AI-102** ([retirement table in the same post](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128)).

**However:** a dedicated **credential** or **exam** landing page for **AI-103** on **learn.microsoft.com** may **not be published yet** (searching the credentials catalog / typical exam URLs can return nothing or 404 until Microsoft ships the page).

**What *is* on Learn today (related):**

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:18%;">On Learn</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:42%;">URL</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:40%;">What it is</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Course AI-103T00-A</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><a href="https://learn.microsoft.com/en-us/training/courses/ai-103t00">Develop AI apps and agents on Azure</a></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>Training course</b> (not the exam page) • aligns with Foundry / agents • availability per course page</td>
</tr>
</tbody>
</table>

**Action:** For **Exam AI-103** scheduling, study guide, and skill outline, watch [Microsoft Learn credentials](https://learn.microsoft.com/en-us/credentials/) and [Skills Hub Blog](https://techcommunity.microsoft.com/category/skills-hub/blog/skills-hub-blog) until the exam is listed.

---

## How these three relate (important)

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:38%;">Retiring / legacy</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:62%;">Replacement in Microsoft’s <b>blog</b> roadmap</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Exam AI-102</b> (Azure AI Engineer Associate)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>Exam AI-103</b> — <i>Azure AI App and Agent Developer Associate</i> (Foundry, agents, GenAI apps)—<b>not</b> AI-200 <small>(exam page on Learn: verify when live)</small></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Exam AZ-204</b> (Azure Developer Associate)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><b>Exam AI-200</b> — <i>Azure AI Cloud Developer Associate</i></td>
</tr>
</tbody>
</table>

So **AI-200** is the **cloud-native developer** track (containers, data planes for AI, events, observability), while the **announced** successor to **AI-102** is **AI-103** for “implement Azure AI / Foundry / agents”—but **prepare using the blog + AI-103T00 course** until Learn publishes **Exam AI-103**. This doc compares **AI-102** vs **AI-200** vs **Agentic Architect** because you asked for those three by name.

---

## Quick evaluation

### 1. Is **Exam AI-200** more suitable than **AI-102** nowadays?

- **Different roles:** Per Microsoft’s **Skills Hub blog**, **AI-102** is being retired in favor of **Exam AI-103** for the **Azure AI engineer** line (see **⚠** note above—**exam listing on Learn may lag** the blog); **AI-200** replaces **AZ-204** for developers building **AI solutions on Azure** with emphasis on **containerized compute, vector-enabled databases, event-driven pipelines, serverless, secrets, observability** ([Skills Hub Blog](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128)).
- **If your job is “backend + K8s/ACA + pgvector + events + monitoring” for AI apps:** **AI-200** is the **forward-looking** credential (once live)—aligned with [Course AI-200T00-A](https://learn.microsoft.com/en-us/training/courses/ai-200t00).
- **If your job is “Azure AI services, Search, OpenAI, agents in Foundry”:** Microsoft’s **roadmap** names **AI-103** (not AI-200) as the **AI-102** replacement—use **[AI-103T00](https://learn.microsoft.com/en-us/training/courses/ai-103t00)** and Learn paths until the **Exam AI-103** page appears ([blog](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128)).
- **AI-102** remains valid until retirement (**June 30, 2026** per [Azure AI Engineer](https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/)) if you need the **current** associate badge immediately.

### 2. **Agentic AI Business Solutions Architect**

- **Advanced** architect cert; **Dynamics / Power Platform / Copilot Studio / Foundry** at enterprise scope ([cert page](https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/)).
- **Prerequisites** include **AI-102** or many Dynamics/Power associates—not AI-200 ([prerequisite list](https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/)).
- **Exam AB-100**, 100 minutes.

---

## Comparison table (AI-102 vs AI-200 vs Agentic Architect)

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:14%;">Aspect</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:29%;">Azure AI Engineer Associate<br><small>Exam AI-102</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:29%;">Azure AI Cloud Developer Associate<br><small>Exam AI-200</small></th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:28%;">Agentic AI Business Solutions Architect<br><small>Exam AB-100</small></th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Credential focus</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Design &amp; implement Azure AI: vision • NLP • knowledge mining • GenAI • agents <small>(<a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/">Learn</a>)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Build, integrate, monitor AI on Azure: <span style="background:#e3f2fd;padding:1px 3px">containers</span> • <span style="background:#e3f2fd;padding:1px 3px">vector DBs</span> • <span style="background:#fff3e0;padding:1px 3px">event-driven</span> • serverless • secrets • <span style="background:#c8e6c9;padding:1px 3px">observability</span> <small>(<a href="https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128">Skills Hub</a>)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;">AI-first <b>solution architecture</b> • agentic / multi-agent • D365 / Power / Foundry • security • ROI <small>(<a href="https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/">Learn</a>)</small></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Official links</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><a href="https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/">Azure AI Engineer</a></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Exam/cred: check Learn when GA • Prep: <a href="https://learn.microsoft.com/en-us/training/courses/ai-200t00">AI-200T00-A</a></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;"><a href="https://learn.microsoft.com/en-us/credentials/certifications/agentic-ai-business-solutions-architect/">Agentic AI Architect</a></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Level</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Intermediate (Associate)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Intermediate (Associate)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;">Advanced</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Microsoft-stated timing</b> <small>(planned)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#ffebee;vertical-align:top;"><span style="background:#ffcdd2;padding:2px 4px">⚠</span> Retires <b>June 30, 2026</b> • <b>AI-103</b> announced as replacement—<b>confirm on Learn</b> • prep: <a href="https://learn.microsoft.com/en-us/training/courses/ai-103t00">AI-103T00</a></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Beta &amp; training <b>Apr 2026</b>; go-live <b>Jul 2026</b> <small>(blog)</small> • course <b>4/30/26</b> <small>(<a href="https://learn.microsoft.com/en-us/training/courses/ai-200t00">AI-200T00</a>)</small> • replaces <b>AZ-204</b> (Jul 31, 2026)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;">Active • exam 100 min</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Replaces / prerequisite</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Legacy “Azure AI engineer” associate</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Replacement for <b>Azure Developer (AZ-204)</b> in AI-heavy dev work</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;">Requires prior cert(s)—includes <b>AI-102</b> or Power/Dynamics associates</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Training highlight</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Learn paths + AI-102 study guide</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#c8e6c9;padding:2px 4px">✓</span> <a href="https://learn.microsoft.com/en-us/training/courses/ai-200t00">AI-200T00</a>: ACA • AKS • Cosmos DB • PostgreSQL+pgvector • Managed Redis • Functions • Service Bus • secrets • observe/troubleshoot</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;">Study guide AB-100 • “No training available” on cert page <small>(check Learn)</small></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>FRU</b> <small>(fru-genai-analytics-new)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><span style="background:#fff9c4;padding:2px 4px">Conceptual</span> Azure OpenAI / Search / AI services—repo not Azure-deployed today</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><span style="background:#2e7d32;color:white;padding:1px 4px">recommended</span> <b>parallel skills</b>: K8s/ACA • pgvector • events • observability—closest to how you ship backends</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;"><span style="background:#ffcdd2;padding:2px 4px">Low</span> unless career is Microsoft business-app architecture</td>
</tr>
</tbody>
</table>

---

## Also consider: announced **Exam AI-103** (AI-102 successor for Foundry/agents)—blog only until Learn lists it

If your goal is **“what replaces AI-102 for Azure AI / Foundry / agents,”** Microsoft’s **Skills Hub** table names **Azure AI App and Agent Developer Associate (Exam AI-103)**—beta Apr 2026, go-live Jun 2026 ([blog](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128)). That is **not** the same as **AI-200**.

**Why you might not find “Exam AI-103” on Azure’s site yet:** the **exam and certification pages are often published later** than the blog announcement. Until **learn.microsoft.com** shows **Exam AI-103** (or the new cert name) in the credentials catalog, treat the blog as the **intent** and use **[Course AI-103T00-A](https://learn.microsoft.com/en-us/training/courses/ai-103t00)** plus Learn learning paths (e.g. “AI apps and agents on Azure”) for **skills**, not as proof the exam is bookable today.

---

## Note: Exam AI-103 vs AI-102 — overlap and likely differences

**What we can compare today:** **AI-102** has a full **[exam study guide (Skills measured)](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-102)** (e.g. updated **Dec 23, 2025**). **Exam AI-103** does not yet have an equivalent public “Skills measured” page on Learn in many cases—only **[Course AI-103T00-A](https://learn.microsoft.com/en-us/training/courses/ai-103t00)** plus the **[Skills Hub Blog](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128)** roadmap. Anything below about **AI-103 exam weighting** is **inference** until Microsoft publishes the official AI-103 exam outline.

### Summary

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:22%;">Question</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:78%;">Answer</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Totally different stacks?</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>No.</b> Current <b>AI-102</b> skills are already <b>Microsoft Foundry–oriented</b>: plan/manage Foundry • <b>generative AI</b> (hub/project, RAG, prompt flow, eval, SDK) • <b>Azure OpenAI in Foundry Models</b> • multimodal • <b>agentic</b> area (~5–10%): Foundry Agent Service, Agent Framework, multi-agent orchestration (<a href="https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-102">AI-102 study guide</a>).</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Much different exam emphasis?</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><b>Possibly.</b> <b>AI-102</b> still has large areas for <b>vision</b>, <b>NLP/speech</b>, <b>knowledge mining</b> (Search, Document Intelligence). <b>AI-103T00</b> is framed on Foundry • GenAI apps • agents • knowledge/tools in agentic apps • multimodal—suggesting <b>AI-103</b> may stress <b>app + agent dev</b> more than full multimodal breadth of AI-102. <b>Confirm when AI-103 skills publish.</b></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Studied AI-102 deeply—reset for AI-103?</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>No</b> for core Foundry/GenAI/RAG/agents—reuse most of that. Plan <b>deltas</b> once official AI-103 exam guide exists.</td>
</tr>
</tbody>
</table>

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:16%;">Source</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:42%;">AI-102</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:42%;">AI-103 (today)</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Official artifact</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Exam + <a href="https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/ai-102">study guide / skills measured</a></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><a href="https://learn.microsoft.com/en-us/training/courses/ai-103t00">Course AI-103T00-A</a> + blog • exam detail page may lag</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Breadth</b></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;">Broad <b>Azure AI engineer</b>: Foundry + GenAI + agents + vision + NLP + search/documents <small>(study guide)</small></td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;">Course signals <b>app/agent-first</b> Foundry work • final exam scope TBD</td>
</tr>
</tbody>
</table>

---

## Which should you pick? (summary)

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:40%;">Your goal</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:60%;">Choose</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;">Need <b>Azure AI engineer</b> credential <b>before</b> mid-2026</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><b>AI-102</b>, then <b>AI-103</b> when listed on Learn—or build skills with <a href="https://learn.microsoft.com/en-us/training/courses/ai-103t00">AI-103T00</a> while waiting</td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;">Validate <b>cloud dev</b> for AI (containers, vectors, events, ops)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><b>AI-200</b> + <a href="https://learn.microsoft.com/en-us/training/courses/ai-200t00">AI-200T00</a></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;"><b>Enterprise architect</b> for agentic Microsoft business solutions</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#fff3e0;vertical-align:top;"><b>Agentic AI Business Solutions Architect</b> (after prerequisites)</td>
</tr>
</tbody>
</table>

---

## Related in-repo

<table style="width:100%;border-collapse:collapse;font-size:12px;">
<thead>
<tr>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:28%;">Doc</th>
<th style="border:1px solid #BFCAD6;padding:6px;background:#1565c0;color:white;text-align:left;width:72%;">Path</th>
</tr>
</thead>
<tbody>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;">Four-cloud comparison</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F8FBFF;vertical-align:top;"><a href="ai_ml_cert_comparison_four_clouds.md">ai_ml_cert_comparison_four_clouds.md</a></td>
</tr>
<tr>
<td style="border:1px solid #D7E0EA;padding:6px;background:#e3f2fd;vertical-align:top;">OpenAI-style cert comparison (incl. §4 architect)</td>
<td style="border:1px solid #D7E0EA;padding:6px;background:#F4FFF6;vertical-align:top;"><a href="OPENAI_results_certification_comparison_2026.md">OPENAI_results_certification_comparison_2026.md</a></td>
</tr>
</tbody>
</table>

---

*Supersedes the previous draft that compared AI-103T00 (course) instead of Exam AI-200. **Exam AI-103** may appear on Learn after blog announcements—verify on [Microsoft Learn Credentials](https://learn.microsoft.com/en-us/credentials/) and the [Skills Hub Blog](https://techcommunity.microsoft.com/blog/skills-hub-blog/the-ai-job-boom-is-here-are-you-ready-to-showcase-your-skills/4494128).*
