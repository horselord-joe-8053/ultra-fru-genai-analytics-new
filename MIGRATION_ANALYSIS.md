# FRU GenAI Analytics: Legacy → New Project Migration Analysis

## Executive Summary

The **fru-genai-analytics-new** project is a modern refactoring of **fru-genai-analytics-legacy**, with primary focus on Infrastructure as Code (IaC) organization and deployment simplification. The **core-app/** directory in the new project is currently a placeholder and does NOT yet contain the sophisticated backend, frontend, and agent logic from the legacy project's **module_app_core/**.

### Key Gap
- **Legacy**: Full feature-rich application in `module_app_core/` with 900+ line API, React frontend, agent-based query processing, and complex analytics pipelines
- **New**: IaC-first architecture with deployment scaffolding but **missing the actual application code**

---

## 1. Architecture Overview

### New Project Structure (fru-genai-analytics-new)
```
fru-genai-analytics-new/
├── core-app/                    # ← APPLICATION CODE (Currently minimal placeholder)
│   ├── analytics/               # ← Spark + Delta jobs (minimal scaffold)
│   │   ├── jobs/
│   │   │   ├── bootstrap.py     # Dummy 100-record bootstrap
│   │   │   └── periodic.py      # Dummy periodic job
│   │   └── docker/
│   │       └── Dockerfile       # Multi-stage Spark image
│   └── public/index.html        # Empty placeholder
│
├── deploy-aws/
│   ├── shared/
│   │   ├── durable/             # VPC, IAM, KMS, secrets (rarely destroyed)
│   │   └── nondurable/          # Buckets, ECR, logs (frequently destroyed)
│   ├── kube/                    # EKS deployment
│   └── nonkube/                 # ECS deployment
├── deploy-gcp/                  # GCP parity
└── infra-modules/               # Reusable Terraform modules
```

### Legacy Project Structure (fru-genai-analytics-legacy)
```
fru-genai-analytics-legacy/
├── module_app_core/             # ← APPLICATION CODE (Feature-rich, needs migration)
│   ├── backend/                 # Flask API
│   │   ├── api/app.py           # 917 lines: main Flask application
│   │   ├── llm/                 # LLM integration
│   │   │   └── bedrock_client.py# AWS Bedrock + Claude API fallback
│   │   ├── agents/              # ReAct agent for query processing
│   │   │   ├── query_agent.py   # 910 lines: autonomous agent
│   │   │   ├── tools/           # Agent tools (SQL, semantic search, SQL generator)
│   │   │   └── metrics.py       # Agent performance metrics
│   │   ├── etl/                 # ETL utilities
│   │   ├── services/            # Analytics scheduler, save to DB
│   │   ├── utils/               # Helper utilities
│   │   ├── env_utils/           # Environment variable handling
│   │   └── requirements.txt
│   ├── frontend/                # React + TypeScript + Vite
│   │   ├── src/
│   │   │   ├── App.tsx          # Chat UI + analytics
│   │   │   └── components/
│   │   └── vite.config.ts       # Proxy to backend API
│   └── spark_jobs/              # PySpark batch analytics
│       ├── ingest_delta.py      # CSV → Delta Lake
│       ├── run_analytics.py     # Batch analytics transform
│       ├── generate_training_data.py
│       └── scheduler.py          # Background job scheduler
```

---

## 2. Core Application Components That Need Migration

### 2.1 Backend API (Flask)
**Location in Legacy**: `module_app_core/backend/api/app.py` (917 lines)

**Key Features**:
- `/query` endpoint: Natural language question → pgvector ANN search → LLM synthesis
- `/analytics` endpoint: Batch analytics results from PostgreSQL
- `/health` endpoint: Database, OpenAI, AWS credential status checks
- Database connection pooling with connection timeout
- CORS configuration with environment-driven allowed origins
- Input validation and sanitization
- Structured error handling with logging
- Token usage tracking (Bedrock + Claude API)
- Request/response JSON serialization with Decimal/Date handling

**Integration Points**:
- PostgreSQL (pgvector): Semantic search over sales embeddings + feedback
- OpenAI API: Text embedding generation
- AWS Bedrock: Claude LLM for response synthesis
- Claude API: Local development fallback

---

### 2.2 LLM Integration Layer
**Location in Legacy**: `module_app_core/backend/llm/bedrock_client.py` (275 lines)

**Key Features**:
- Dual-mode: Claude API (local dev) + AWS Bedrock (production)
- AWS profile-aware (local dev with AWS_PROFILE vs IAM role in ECS/EKS)
- Inference profile support (Claude 3.5+) vs model ID fallback
- Token usage tracking from both APIs
- Robust error handling (ClientError, BotoCoreError, JSON parsing)
- Response truncation warnings (max_tokens reached)
- Line 1-275: Complete Bedrock/Claude integration with fallbacks

**This is a critical, production-tested piece that must be preserved**.

---

### 2.3 Agent-Based Query Processing (ReAct)
**Location in Legacy**: `module_app_core/backend/agents/query_agent.py` (910 lines)

**Key Features**:
- **Autonomous query planning**: Agent decides which tools to use
- **Tool orchestration** (3 core tools):
  - `execute_sql`: Run SQL against PostgreSQL
  - `semantic_search`: pgvector ANN search over embeddings
  - `generate_sql`: LLM-generated SQL from natural language
- **Iterative ReAct loop**: Thought → Action → Observation → next iteration (max 5 iterations)
- **Synthesis**: Combines results into natural language response
- **Metrics/logging**: Agent performance tracking across iterations
- **Feature flag**: `USE_AGENT_QUERY` env var enables/disables agent mode

**Represents sophisticated autonomous reasoning** — goes beyond simple pgvector search.

---

### 2.4 Frontend (React + Vite)
**Location in Legacy**: `module_app_core/frontend/` (~500 lines of React/TS)

**Key Features**:
- Chat-based UI: User questions + AI responses
- Dual-panel layout: Chat on left, analytics on right
- Real-time batch analytics display:
  - Sales by brand, store performance, feedback distribution
  - Price statistics, top models
  - Negative feedback rate tracking
- Vite dev proxy: `/query` → `http://localhost:5000` (for local dev)
- Error handling with user-friendly messages
- Build tooling: TypeScript, Tailwind CSS, PostCSS

---

### 2.5 Spark + Delta Analytics Pipeline
**Location in Legacy**: `module_app_core/spark_jobs/` + `backend/services/`

**Key Components**:

#### `ingest_delta.py`
- CSV → Delta Lake (Spark DataFrame)
- Used for initial data loading

#### `run_analytics.py`
- **6 batch analytics jobs**:
  1. Sales summary by brand (count, revenue, avg/min/max price)
  2. Store performance (sales, revenue, negative feedback rate)
  3. Feedback analysis by brand
  4. Monthly sales trends (time series)
  5. Top models by sales volume
  6. Price distribution statistics
- Saves results to PostgreSQL `batch_analytics` table
- Optional JSON backup output

#### `analytics_scheduler.py`
- APScheduler background job runner
- Runs `run_analytics.py` on interval (default 5 min)
- Configured via `ENABLE_ANALYTICS_SCHEDULER` env var
- Subprocess-based execution with timeout (5 min)

#### `save_analytics_to_db.py`
- Persists analytics results to PostgreSQL
- Stores JSONB fields for complex structures

---

### 2.6 Environment & Configuration
**Location in Legacy**: `backend/env_utils/`, `backend/utils/env_helpers.py`

**Key Patterns**:
- Environment-driven configuration (all secrets from env vars)
- Required vs optional env vars with defaults
- Type-safe env var parsing (int, bool, string)
- Database credentials, API keys, AWS region, log level

---

## 3. Current State: New Project

### Placeholder Spark Jobs
**Location**: `core-app/analytics/jobs/`

**Current State**:
- `bootstrap.py`: Writes 100-row dummy data to Delta Lake
- `periodic.py`: Reads dummy data back (no real analytics)
- **No connection** to actual business logic from legacy

### Missing Components
1. ❌ Flask API (backend/api/app.py)
2. ❌ LLM integration (backend/llm/)
3. ❌ Agent-based query processing (backend/agents/)
4. ❌ React frontend (frontend/)
5. ❌ Real analytics pipeline (spark_jobs/)
6. ❌ Backend services (analytics_scheduler, save_analytics_to_db)
7. ❌ Environment utilities (env_utils/ package)
8. ❌ Database utilities and connection pooling

### What IS Present
1. ✅ IaC/deployment structure (deploy-aws/, deploy-gcp/)
2. ✅ Dockerfile scaffolding for analytics container
3. ✅ Orchestrator.py for deployment automation

---

## 4. Migration Roadmap

### Phase 1: Backend API & LLM Integration
**Migrate to**: `core-app/backend/`

**Steps**:
1. Copy `module_app_core/backend/llm/bedrock_client.py` → validate it works
2. Copy `module_app_core/backend/utils/env_helpers.py` → environment handling
3. Copy `module_app_core/backend/api/app.py` → main Flask application
   - Update imports to reflect new directory structure
   - Keep all 917 lines of logic intact
4. Copy LLM client factory and supporting utilities
5. Create Docker image for backend (Dockerfile for Python 3.10+ with Flask, Bedrock SDK)

**Output**: Containerized Flask API with full `/query`, `/analytics`, `/health` endpoints

---

### Phase 2: Agent-Based Query Processing
**Migrate to**: `core-app/backend/agents/`

**Steps**:
1. Copy `module_app_core/backend/agents/query_agent.py` (910 lines of sophistication)
2. Copy all agent tools: `sql_tool.py`, `semantic_search_tool.py`, `sql_generator_tool.py`
3. Copy prompts, metrics, logger modules
4. Connect to Flask API in Phase 1
5. Test with `USE_AGENT_QUERY=true` feature flag

**Output**: Agent-based autonomous query planning and execution

---

### Phase 3: Frontend (React + Vite)
**Migrate to**: `core-app/frontend/`

**Steps**:
1. Copy entire `module_app_core/frontend/` → `core-app/frontend/`
2. Update build tooling as needed
3. Ensure vite proxy still points to backend API (URL TBD based on deployment)
4. Create Dockerfile for frontend (Node.js build + static server)

**Output**: Chat UI + analytics dashboard

---

### Phase 4: Real Spark Analytics Pipeline
**Migrate to**: `core-app/analytics/jobs/`

**Steps**:
1. Replace `bootstrap.py` with real data ingestion logic
   - Should read actual CSV (or S3) data
   - Transform to Delta table schema matching business logic
2. Replace `periodic.py` with `run_analytics.py` (batch analytics)
3. Copy `ingest_delta.py` → delta loading utilities
4. Copy `generate_training_data.py` → NLQ→SQL training data generation
5. Update scheduler integration: analytics_scheduler.py → runs periodically

**Output**: Real batch analytics over Spark + Delta, results persisted to PostgreSQL

---

### Phase 5: Database & Service Layer
**Migrate to**: `core-app/backend/services/`

**Steps**:
1. Copy `save_analytics_to_db.py` → persist analytics results
2. Copy `analytics_scheduler.py` → background job orchestration
3. Create schema migration scripts:
   - `batch_analytics` table (JSONB fields for results)
   - `fru_sales_embeddings` table (pgvector for semantic search)
4. Test connection pooling, timeouts, error handling

**Output**: Persistent analytics storage + scheduled job execution

---

### Phase 6: Environment & Secrets
**Migrate to**: `core-app/.env.example`, deployment config

**Required Env Vars** (migrate to deployment IaC):
```env
# Database
PGHOST=...
PGPORT=5432
PGUSER=...
PGPASSWORD=...
PGDATABASE=...

# APIs
OPENAI_API_KEY=...
AWS_REGION=...
AWS_BEDROCK_MODEL_ID=...          # or AWS_BEDROCK_INFERENCE_PROFILE_ID

# Feature Flags
USE_AGENT_QUERY=true              # Enable autonomous agent
ENABLE_ANALYTICS_SCHEDULER=true   # Run batch analytics
ANALYTICS_SCHEDULER_INTERVAL_MINUTES=5

# Deployment
ALLOWED_ORIGINS=http://localhost:5173,https://fru.yourdomain.com
LOG_LEVEL=INFO
CONTAINER_TYPE=ecs               # or 'kube' or 'local'
```

**Output**: Environment configuration templates + secrets manager integration (AWS Secrets Manager, Azure Key Vault, etc.)

---

## 5. Key Architectural Decisions in New Project

### IaC-First Approach
- All infrastructure is code (OpenTofu/Terraform)
- Modular design: shared durable vs shared nondurable vs deployment-specific
- Scope isolation: kube teardown doesn't break nonkube and vice versa
- State management with remote backends

### Containerization
- Backend: Python 3.10+ with Flask + Bedrock SDK
- Frontend: Node.js build + static server
- Analytics: Spark 3.5 with Delta Lake package

### Deployment Strategies
- **EKS (kube)**: Kubernetes + CronJob for analytics scheduler
- **ECS (nonkube)**: Fargate + EventBridge for analytics scheduler
- **Local**: Docker Compose for dev

### Observability
- CloudWatch logs by default
- Agent metrics tracking (iterations, tool usage)
- Health checks at component level

---

## 6. Critical Preservation Points

These are **non-negotiable** features from legacy that MUST be preserved:

1. ✅ **Bedrock + Claude API dual-mode**: Local dev vs production seamlessly
2. ✅ **Agent-based planning**: Autonomous query reasoning (not just pgvector lookup)
3. ✅ **Token tracking**: Understanding LLM cost and efficiency
4. ✅ **Error handling**: Robust fallbacks and user-facing error messages
5. ✅ **Batch analytics**: Heavy lifting on Spark, results cached in PostgreSQL
6. ✅ **Security**: Input validation, CORS, environment-driven secrets
7. ✅ **Observability**: Detailed logging for troubleshooting

---

## 7. Files to Migrate (Legacy → New)

### Backend (~4000 lines total)
```
module_app_core/backend/
├── api/
│   └── app.py                    → core-app/backend/api/app.py
├── llm/
│   ├── bedrock_client.py         → core-app/backend/llm/bedrock_client.py
│   └── client_factory.py         → core-app/backend/llm/client_factory.py
├── agents/
│   ├── query_agent.py            → core-app/backend/agents/query_agent.py
│   ├── tools/                    → core-app/backend/agents/tools/
│   ├── prompts.py                → core-app/backend/agents/prompts.py
│   ├── metrics.py                → core-app/backend/agents/metrics.py
│   └── logger.py                 → core-app/backend/agents/logger.py
├── services/
│   ├── analytics_scheduler.py    → core-app/backend/services/analytics_scheduler.py
│   └── save_analytics_to_db.py   → core-app/backend/services/save_analytics_to_db.py
├── utils/
│   └── env_helpers.py            → core-app/backend/utils/env_helpers.py
├── env_utils/                    → core-app/backend/env_utils/
└── requirements.txt              → core-app/requirements.txt
```

### Frontend (~500 lines)
```
module_app_core/frontend/
├── src/
│   ├── App.tsx                   → core-app/frontend/src/App.tsx
│   ├── components/               → core-app/frontend/src/components/
│   └── utils/                    → core-app/frontend/src/utils/
├── vite.config.ts                → core-app/frontend/vite.config.ts
├── tsconfig.json                 → core-app/frontend/tsconfig.json
├── package.json                  → core-app/frontend/package.json
└── tailwind.config.js            → core-app/frontend/tailwind.config.js
```

### Spark + Analytics (~700 lines)
```
module_app_core/spark_jobs/
├── ingest_delta.py               → core-app/analytics/jobs/ingest_delta.py
├── run_analytics.py              → core-app/analytics/jobs/run_analytics.py
├── generate_training_data.py     → core-app/analytics/jobs/generate_training_data.py
└── scheduler.py                  → core-app/analytics/scheduler.py
```

---

## 8. Effort Estimate

| Component | LOC | Difficulty | Est. Effort |
|-----------|-----|-----------|-------------|
| Backend API | 917 | Medium | 2-3 days |
| LLM Integration | 275 | Medium | 1 day |
| Agent Query Processing | 910 | High | 3-4 days |
| Frontend | 500 | Medium | 2-3 days |
| Spark Analytics | 700 | Medium | 2 days |
| Services Layer | 200+ | Low | 1 day |
| Environment Setup | N/A | Low | 1 day |
| **Total** | **~4000** | **Medium** | **~2 weeks** |

---

## 9. Integration Points with New Project Structure

### How It Fits Into IaC
1. **Backend container**: Built from `core-app/backend/Dockerfile`, pushed to ECR
   - ECS deploy: Fargate task definition references ECR image
   - EKS deploy: Kubernetes deployment manifests reference ECR image
2. **Frontend**: Built from `core-app/frontend/Dockerfile`, pushed to ECR
   - ECS: Fargate service with ALB routing
   - EKS: Kubernetes service with ingress
3. **Spark jobs**: Built from `core-app/analytics/docker/Dockerfile`
   - ECS: EventBridge → ECS RunTask (see `deploy-aws/nonkube/main.tf` line 120)
   - EKS: CronJob scheduling (see `deploy-aws/kube/`)
4. **Environment config**: Injected via:
   - ECS task definition env vars (from secrets store reference)
   - Kubernetes ConfigMap + Secret mounts

---

## 10. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Database schema mismatch | High | Compare `fru_sales_embeddings` table definitions early |
| Bedrock API changes | Medium | Keep vendor SDK up-to-date, use inference profiles |
| Agent complexity | High | Preserve all 910 lines, add comprehensive unit tests |
| Frontend API routing | Medium | Ensure deployment sets correct `VITE_API_BASE_URL` |
| Scheduler timing | Medium | Test bootstrap + periodic runs separately |

---

## Summary

The new project's **core-app/** is currently a **deployment-focused refactor** lacking the actual sophisticated application logic from the legacy. A ~2 week effort to migrate:

- ✅ 917-line Flask API with full pgvector + LLM integration
- ✅ 910-line ReAct agent for autonomous query planning
- ✅ React frontend with chat UI + analytics dashboard
- ✅ Spark batch analytics with Delta Lake + PostgreSQL persistence
- ✅ Robust error handling, logging, observability

will result in a **production-ready next-gen infrastructure + application system** that preserves all the sophisticated GenAI reasoning logic while leveraging modern IaC practices.

