# Shared Fundamentals — Deep Study Plan with Free Materials

> Study once, apply across AWS, GCP, and OCI. All links below are free (audit/free tier or open docs).

---

## 1. ML Fundamentals

**Concepts:** supervised/unsupervised learning, overfitting/underfitting, bias-variance, train/val/test split, cross-validation, regularization (L1/L2), gradient descent, loss functions, feature scaling, one-hot encoding, baseline models.

### Free materials

| Resource | Link | Notes |
|----------|------|-------|
| **scikit-learn User Guide** | [https://scikit-learn.org/stable/user_guide.html](https://scikit-learn.org/stable/user_guide.html) | Official; model evaluation, cross-validation, preprocessing |
| **scikit-learn Preprocessing** | [https://scikit-learn.org/stable/modules/preprocessing.html](https://scikit-learn.org/stable/modules/preprocessing.html) | Scaling, encoding, transformers |
| **Coursera – Machine Learning Foundations** | [https://www.coursera.org/learn/ml-foundations](https://www.coursera.org/learn/ml-foundations) | UW; free audit; case-study approach |
| **Coursera – Machine Learning Basics** | [https://www.coursera.org/learn/machine-learning-basics](https://www.coursera.org/learn/machine-learning-basics) | 1 week; Python, linear regression, KNN |
| **Udacity – Intro to ML** | [https://www.udacity.com/course/intro-to-ml--ud120](https://www.udacity.com/course/intro-to-ml--ud120) | Free; naive Bayes, SVMs, decision trees, clustering |
| **Interview Q&A (local)** | [senior_ai_mlops_interview_100_colored.md](../interviews/senior_ai_mlops_interview_100_colored.md) §1–3 | ML Fundamentals, Evaluation, Data/Drift |

### Suggested order

1. Read scikit-learn preprocessing + model evaluation (2–3 hrs).
2. Skim Coursera ML Foundations or Udacity Intro (4–6 hrs).
3. Drill interview Q&A §1–3 for verbal fluency.

---

## 2. Data Prep & Feature Engineering

**Concepts:** data formats (Parquet, JSON, CSV, ORC), ingestion, cleaning, outlier handling, imputation, deduplication, scaling, normalization, one-hot/label/target encoding, binning, feature selection, feature stores, data quality, bias metrics.

### Free materials

| Resource | Link | Notes |
|----------|------|-------|
| **scikit-learn Preprocessing** | [https://scikit-learn.org/stable/modules/preprocessing.html](https://scikit-learn.org/stable/modules/preprocessing.html) | StandardScaler, OneHotEncoder, pipelines |
| **scikit-learn Data Transforms** | [https://sklearn.org/stable/data_transforms.html](https://sklearn.org/stable/data_transforms.html) | Dataset transformations |
| **scikit-learn Preprocessing Examples** | [https://sklearn.org/stable/auto_examples/preprocessing/index.html](https://sklearn.org/stable/auto_examples/preprocessing/index.html) | Code examples |
| **Coursera – Fundamentals of ML** | [https://www.coursera.org/learn/fundamentals-of-machine-learning-ml](https://www.coursera.org/learn/fundamentals-of-machine-learning-ml) | Data preprocessing, AWS/Azure integration; free audit |
| **Exam guides (local)** | `aws_machine-learning-engineer-associate-01.pdf` Domain 1; `gcp_professional_machine_learning_engineer_exam_guide_english_3.1_final.pdf` §2 | Cloud-specific data prep tasks |

### Suggested order

1. scikit-learn preprocessing docs + 2–3 examples (2 hrs).
2. Review AWS Domain 1 / GCP §2 for cloud service mapping (1 hr).
3. Map to project: `core_app/analytics/`, feature store concepts.

---

## 3. LLM & RAG

**Concepts:** LLM architectures, prompting, fine-tuning, tokenization, RAG pipeline (chunk → embed → retrieve → generate), context window, hallucinations, chain-of-thought.

### Free materials

| Resource | Link | Notes |
|----------|------|-------|
| **LangChain RAG Tutorial** | [https://python.langchain.com/docs/tutorials/rag](https://python.langchain.com/docs/tutorials/rag) | Official; build RAG from scratch, ~40 lines |
| **BuildRag – RAG from Scratch** | [https://buildrag.com/tutorials/build-your-first-rag/build-rag-from-scratch](https://buildrag.com/tutorials/build-your-first-rag/build-rag-from-scratch) | Step-by-step without high-level libs |
| **OCI GenAI repo – 01.fundamentals** | [https://github.com/LeonSilva15/oci-generative-ai/tree/master/01.fundamentals](https://github.com/LeonSilva15/oci-generative-ai/tree/master/01.fundamentals) | LLM fundamentals, prompts, fine-tuning |
| **OCI GenAI repo – 03.blocks-for-llm-apps** | [https://github.com/LeonSilva15/oci-generative-ai/tree/master/03.blocks-for-llm-apps](https://github.com/LeonSilva15/oci-generative-ai/tree/master/03.blocks-for-llm-apps) | RAG, LangChain, memory, chains |
| **Google – Intro to GenAI** | [https://cloud.google.com/learn/introduction-to-generative-ai](https://cloud.google.com/learn/introduction-to-generative-ai) | Free learning path |
| **Interview Q&A (local)** | [senior_ai_mlops_interview_100_colored.md](../interviews/senior_ai_mlops_interview_100_colored.md) §6 | LLM / GenAI questions |
| **Project reference** | `core_app/backend/agents/` | QueryAgent, embeddings, Chat UI |

### Suggested order

1. LangChain RAG tutorial (1 hr).
2. OCI 01.fundamentals + 03.blocks-for-llm-apps (2–3 hrs).
3. Trace QueryAgent in project (1 hr).
4. Drill interview §6 for GenAI/RAG.

---

## 4. MLOps Lifecycle

**Concepts:** experiment tracking, model registry, CI/CD for ML, pipelines, deployment (batch vs real-time), versioning, reproducibility, containerization.

### Free materials

| Resource | Link | Notes |
|----------|------|-------|
| **MLOps Zoomcamp (DataTalks.Club)** | [https://courses.datatalks.club/mlops-zoomcamp-2024/](https://courses.datatalks.club/mlops-zoomcamp-2024/) | Free; Docker, AWS, MLflow, Mage, Prometheus, Evidently; [blog](https://datatalks.club/blog/mlops-zoomcamp.html) |
| **MLOps Zoomcamp – GitHub** | [https://github.com/DataTalksClub/mlops-zoomcamp](https://github.com/DataTalksClub/mlops-zoomcamp) | Code, labs, self-paced |
| **Coursera – MLOps & Responsible AI** | [https://www.coursera.org/learn/microsoft-mlops-and-responsible-ai-practices](https://www.coursera.org/learn/microsoft-mlops-and-responsible-ai-practices) | Microsoft; lifecycle, monitoring, CI/CD; free audit |
| **Coursera – DevOps, DataOps, MLOps** | [https://www.coursera.org/learn/devops-dataops-mlops-duke](https://www.coursera.org/learn/devops-dataops-mlops-duke) | Duke; advanced; free audit |
| **Weights & Biases – Effective MLOps** | [https://wandb.ai/site/courses/effective-mlops](https://wandb.ai/site/courses/effective-mlops) | ~4 hrs; pipelines, evaluation |
| **Interview Q&A (local)** | [senior_ai_mlops_interview_100_colored.md](../interviews/senior_ai_mlops_interview_100_colored.md) §4–5 | MLOps lifecycle, serving, system design |
| **Project reference** | `infra_terraform/`, `tools/aws/`, `tools/gcp/` | EKS/GKE, deploy automation |

### Suggested order

1. MLOps Zoomcamp modules 1–3 (Docker, experiment tracking, orchestration) — 6–8 hrs.
2. Skim Coursera MLOps & Responsible AI (2–3 hrs).
3. Map project: CI/CD, Terraform, EKS/GKE.
4. Drill interview §4–5.

---

## 5. Vector DB & Semantic Search

**Concepts:** embeddings, similarity search, ANN vs exact search, IVF, HNSW, FAISS, vector DB sharding, semantic vs keyword search.

### Free materials

| Resource | Link | Notes |
|----------|------|-------|
| **FAISS (Facebook AI)** | [https://github.com/facebookresearch/faiss](https://github.com/facebookresearch/faiss) | Billion-scale vector search; docs + examples |
| **FAISS Wiki** | [https://github.com/facebookresearch/faiss/wiki](https://github.com/facebookresearch/faiss/wiki) | Index types, tuning |
| **Vector DB & Semantic Search (AI for Devs)** | [https://aifordevelopers.io/semantic-search-with-vector-databases/](https://aifordevelopers.io/semantic-search-with-vector-databases/) | Free course; sentence_transformers, embeddings |
| **Milvus + OpenAI** | [https://milvus.io/docs/integrate_with_openai.md](https://milvus.io/docs/integrate_with_openai.md) | Open-source vector DB integration |
| **PostgreSQL pgvector** | [https://github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) | Free; vector extension for Postgres |
| **Elasticsearch Vector Search** | [https://www.elastic.co/search-labs/blog/elastic-vector-database-practical-example](https://www.elastic.co/search-labs/blog/elastic-vector-database-practical-example) | Tutorial with code |
| **System design (local)** | [ai_system_design_top5_solved_colored.md](../interviews/ai_system_design_top5_solved_colored.md) §2, §3 | Vector DB 10B embeddings, Enterprise RAG |
| **Project reference** | `core_app/backend/agents/` | Embeddings for agent queries |

### Suggested order

1. FAISS quickstart + AI for Devs semantic search (2–3 hrs).
2. Read system design §2 (Vector DB) and §3 (RAG) (1–2 hrs).
3. Map to project: embedding flow in QueryAgent.

---

## 6. Quick Reference Table

| Topic | Primary free resource | Backup |
|-------|----------------------|--------|
| ML fundamentals | scikit-learn User Guide + [senior_ai_mlops_interview_100_colored.md](../interviews/senior_ai_mlops_interview_100_colored.md) §1–3 | Coursera ML Foundations |
| Data prep & features | scikit-learn preprocessing | Coursera Fundamentals of ML |
| LLM & RAG | [LangChain RAG](https://python.langchain.com/docs/tutorials/rag) + OCI 01, 03 | BuildRag, Google GenAI path |
| MLOps | [MLOps Zoomcamp](https://datatalks.club/courses/2024/mlops-zoomcamp.html) | Coursera MLOps & Responsible AI |
| Vector DB & semantic search | [FAISS](https://github.com/facebookresearch/faiss) + [AI for Devs](https://aifordevelopers.io/semantic-search-with-vector-databases/) | ai_system_design_top5 §2, §3 |

---

## 7. Estimated Time (Full-Time)

| Topic | Min | Max |
|-------|-----|-----|
| ML fundamentals | 4 | 8 |
| Data prep & features | 2 | 4 |
| LLM & RAG | 4 | 6 |
| MLOps lifecycle | 8 | 12 |
| Vector DB & semantic search | 3 | 5 |
| **Total** | **~21** | **~35** |

Hours. Adjust based on prior experience.
