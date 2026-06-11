# AI Certification Study Plan — 3-Week Fast Track (Full-Time)

> **Goal:** Ready for AWS MLA-C01, GCP PMLE, and OCI GenAI in 3 weeks. Assumes full-time study (~8 hrs/day).  
> **Project:** fru-genai-analytics-new | **Shared fundamentals:** See [study_shared_fundamentals.md](study_shared_fundamentals.md)

---

## 1. Overview

| Aspect | Detail |
|--------|--------|
| **Timeline** | 3 weeks, full-time |
| **Strategy** | Week 1: Shared fundamentals + OCI. Week 2: AWS. Week 3: GCP + integration. |
| **Shared fundamentals** | [study_shared_fundamentals.md](study_shared_fundamentals.md) — deep plan with free material links |
| **Interview prep** | [docs/learned/study/interviews/](../interviews/) — 100 MLOps, 50 advanced, 5 system designs |

---

## 2. Week 1: Foundation + OCI GenAI

| Day | Focus | Hours | Resources | Project action |
|-----|-------|-------|-----------|----------------|
| **Mon** | ML fundamentals | 6 | [study_shared_fundamentals.md](study_shared_fundamentals.md) §1; senior_ai_mlops §1–2 | — |
| **Tue** | Data prep, LLM & RAG | 6 | study_shared_fundamentals §2, §3; LangChain RAG, OCI 01, 03 | Trace QueryAgent |
| **Wed** | MLOps, Vector DB | 6 | study_shared_fundamentals §4, §5; MLOps Zoomcamp 1–3 | Map infra_terraform |
| **Thu** | OCI GenAI service | 6 | OCI 02, 04; [LeonSilva15/oci-generative-ai](https://github.com/LeonSilva15/oci-generative-ai) | Optional: OCI endpoint |
| **Fri** | OCI practice + interview drill | 6 | OCI practice exam; senior_ai_mlops §6 | — |
| **Sat** | Consolidate + weak areas | 4 | Review study_shared_fundamentals; senior_ai_advanced_50 | — |
| **Sun** | OCI exam (if ready) or rest | — | — | — |

**Week 1 deliverable:** Shared fundamentals solid; OCI GenAI ready to schedule.

---

## 3. Week 2: AWS MLA-C01

| Day | Focus | Hours | Resources | Project action |
|-----|-------|-------|-----------|----------------|
| **Mon** | Data prep (Domain 1) | 6 | AWS exam guide Domain 1; Coursera MLA-C01 | Map S3/Glue in EKS |
| **Tue** | Model dev (Domain 2) | 6 | SageMaker, Bedrock, JumpStart; AWS Domain 2 | Compare Bedrock vs OpenAI |
| **Wed** | Deploy & CI/CD (Domain 3) | 6 | CodePipeline, CodeBuild, EKS; Domain 3 | Relate infra_terraform |
| **Thu** | Monitoring & security (Domain 4) | 6 | CloudWatch, SageMaker Model Monitor; Domain 4 | — |
| **Fri** | AWS practice exams | 6 | AWS Skill Builder, FlashGenius | — |
| **Sat** | Weak areas + interview | 4 | senior_ai_mlops §4–5 | — |
| **Sun** | AWS exam (if ready) or rest | — | — | — |

**Week 2 deliverable:** AWS MLA-C01 ready to schedule.

---

## 4. Week 3: GCP PMLE + Integration

| Day | Focus | Hours | Resources | Project action |
|-----|-------|-------|-----------|----------------|
| **Mon** | BigQuery ML, Vertex AI, AutoML (§1–2) | 6 | GCP exam guide §1–2; Coursera GCP ML | Map tools/gcp/ |
| **Tue** | Scaling, serving, pipelines (§3–5) | 6 | Vertex AI Pipelines, Cloud Build; §3–5 | Compare to AWS deploy |
| **Wed** | Monitoring, responsible AI (§6) | 4 | Vertex AI Model Monitoring; §6 | — |
| **Thu** | GCP practice + system design | 6 | Whizlabs, ExamTopics; ai_system_design_top5 | Design RAG extension |
| **Fri** | Cross-cloud summary + interview | 6 | Create AWS vs GCP vs OCI table; senior_ai_mlops §6–7 | Document parity |
| **Sat** | Final practice exams | 4 | All three certs | — |
| **Sun** | GCP exam (if ready) or buffer | — | — | — |

**Week 3 deliverable:** GCP PMLE ready; cross-cloud summary; interview drill complete.

---

## 5. Daily Rhythm (Full-Time)

| Block | Time | Activity |
|-------|------|----------|
| AM | 4 hrs | Deep study (videos, docs, hands-on) |
| PM | 3 hrs | Practice questions, project integration |
| Eve | 1 hr | Interview Q&A drill, flashcards |

---

## 6. Checklist

- [ ] Week 1: Complete [study_shared_fundamentals.md](study_shared_fundamentals.md); OCI practice; schedule OCI if ready
- [ ] Week 2: AWS Domains 1–4; practice exams; schedule AWS if ready
- [ ] Week 3: GCP §1–6; practice exams; system design; schedule GCP if ready
- [ ] Project: Document RAG flow; cross-cloud parity table

---

## 7. References

| Source | Path |
|-------|------|
| Shared fundamentals (deep) | [study_shared_fundamentals.md](study_shared_fundamentals.md) |
| Main 1–2 month plan | [ai_cert_aws_gcp_oci_1_2mo.md](ai_cert_aws_gcp_oci_1_2mo.md) |
| Interview docs | [../interviews/](../interviews/) |
| Exam guides | `aws_machine-learning-engineer-associate-01.pdf`, `gcp_professional_machine_learning_engineer_exam_guide_english_3.1_final.pdf` |
