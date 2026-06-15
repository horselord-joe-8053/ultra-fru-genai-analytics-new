# Core App

Application code for FRU GenAI Analytics: Flask API, ReAct query agent, React/Vite UI, Spark batch jobs, SQL schema, and sample data.

## Layout

```text
core_app/
├── Dockerfile                 # API image (Flask + nginx static bundle)
├── backend/
│   ├── api/app.py             # Routes: /health, /query, /query/stream, /analytics, /rawdata
│   ├── agents/                # QueryAgent, prompts, tools (generate_sql, execute_sql, semantic_search)
│   ├── env_utils/             # LLM + embedding factories (AWS, GCP, BytePlus, local)
│   ├── services/              # embedding_sync, admin helpers
│   └── etl/                   # CSV → Postgres loaders
├── frontend/                  # React + Vite (chat, execution log, batch analytics, data management)
├── analytics/
│   ├── jobs/run_analytics.py  # Spark → Delta → batch_analytics
│   └── docker/Dockerfile      # Spark image
├── sql/schema_pgvector.sql    # fru_sales_raw, fru_sales_embeddings, batch_analytics
└── data/raw/                  # Sample CSV (fridge_sales_with_rating.csv)
```

## Runtime split

| Lane | Code | Data |
|------|------|------|
| **Interactive** | API + agent + pgvector | `fru_sales_embeddings`, OpenAI/ModelArk embeddings |
| **Batch** | Spark `run_analytics.py` | Delta Lake → `batch_analytics` JSON aggregates |
| **Source of truth** | `/rawdata` CRUD + ETL | `fru_sales_raw` → embeddings + Spark input |

## Deeper docs

- [docs/CORE_APP_STRUCTURE.md](../docs/CORE_APP_STRUCTURE.md) — images, Aurora/Cloud SQL, data-flow diagrams
- [analytics/README.md](analytics/README.md) — Spark schedule, Delta paths, run status
- [README.md](../README.md) — deploy, testing, multi-cloud matrix
