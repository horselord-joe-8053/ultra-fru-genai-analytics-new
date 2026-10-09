CREATE EXTENSION IF NOT EXISTS vector;

-- Raw data source for both query (embeddings) and Spark analytics subsystems.
-- Loaded from CSV at deploy; editable via /rawdata API and Data Management UI.
CREATE TABLE IF NOT EXISTS fru_sales_raw (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    brand TEXT,
    fridge_model TEXT,
    capacity_liters NUMERIC,
    price NUMERIC,
    sales_date DATE,
    store_name TEXT,
    store_address TEXT,
    customer_feedback TEXT,
    feedback_rating INTEGER,
    feedback_sentiment_category TEXT
);

CREATE TABLE IF NOT EXISTS fru_sales_embeddings (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    brand TEXT,
    fridge_model TEXT,
    capacity_liters NUMERIC,
    price NUMERIC,
    sales_date DATE,
    store_name TEXT,
    store_address TEXT,
    customer_feedback TEXT,
    feedback_rating INTEGER,
    feedback_sentiment_category TEXT,
    embedding_openai_1536 VECTOR(1536),
    embedding_skylark_2048 VECTOR(2048)
);

CREATE INDEX IF NOT EXISTS fru_sales_embeddings_ivfflat_openai
ON fru_sales_embeddings
USING ivfflat (embedding_openai_1536 vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS fru_sales_embeddings_customer_id_idx 
ON fru_sales_embeddings(customer_id);

CREATE INDEX IF NOT EXISTS fru_sales_embeddings_store_address_idx 
ON fru_sales_embeddings(store_address);

-- Shared by Kube CronJob and Nonkube EventBridge Spark jobs. See docs/learned/cloud_shared/ANALYTICS_AND_DATA.md.
CREATE TABLE IF NOT EXISTS batch_analytics (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    sales_by_brand JSONB,
    store_performance JSONB,
    feedback_analysis JSONB,
    top_models JSONB,
    price_stats JSONB,
    total_records INTEGER,
    total_revenue NUMERIC
);

-- deploy_scope: which scheduler wrote this row (kube, nonkube). Added for UI "Updated X ago by Nonkube".
ALTER TABLE batch_analytics ADD COLUMN IF NOT EXISTS deploy_scope TEXT;

CREATE INDEX IF NOT EXISTS batch_analytics_created_at_idx
ON batch_analytics(created_at DESC);

-- Singleton: last Spark/scheduler attempt for /analytics run_status UI (local + cloud).
CREATE TABLE IF NOT EXISTS analytics_run_status (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    last_exit_code INTEGER,
    deploy_scope TEXT
);

CREATE INDEX IF NOT EXISTS fru_sales_embeddings_sentiment_category_idx 
ON fru_sales_embeddings(feedback_sentiment_category);

COMMENT ON COLUMN fru_sales_embeddings.feedback_rating IS 
  'Human-reviewed numeric satisfaction rating (1-10) assigned to CUSTOMER_FEEDBACK';
COMMENT ON COLUMN fru_sales_embeddings.feedback_sentiment_category IS 
  'Human-reviewed sentiment category (Positive/Neutral/Negative) assigned to CUSTOMER_FEEDBACK';
