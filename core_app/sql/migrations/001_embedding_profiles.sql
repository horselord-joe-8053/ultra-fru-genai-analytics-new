-- Idempotent migration: legacy embedding column -> profile-named columns.
-- Safe to re-run on deploy (local + cloud). No-op when fru_sales_embeddings does not exist yet.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'fru_sales_embeddings'
  ) THEN
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'fru_sales_embeddings' AND column_name = 'embedding'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'fru_sales_embeddings' AND column_name = 'embedding_openai_1536'
  ) THEN
    ALTER TABLE fru_sales_embeddings RENAME COLUMN embedding TO embedding_openai_1536;
  END IF;

  ALTER TABLE fru_sales_embeddings
    ADD COLUMN IF NOT EXISTS embedding_skylark_2048 VECTOR(2048);

  -- Recreate ivfflat on openai column if index still references old name or missing.
  DROP INDEX IF EXISTS fru_sales_embeddings_ivfflat;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'fru_sales_embeddings' AND column_name = 'embedding_openai_1536'
  ) THEN
    CREATE INDEX IF NOT EXISTS fru_sales_embeddings_ivfflat_openai
      ON fru_sales_embeddings
      USING ivfflat (embedding_openai_1536 vector_cosine_ops)
      WITH (lists = 100);
  END IF;
END $$;

-- Skylark index: create only after backfill (optional manual step).
-- CREATE INDEX ... ON fru_sales_embeddings USING ivfflat (embedding_skylark_2048 ...);
