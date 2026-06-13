# BytePlus ModelArk — local development

## OpenAI search lane (default)

```bash
EMBEDDING_ACTIVE_PROFILE=openai_1536
OPENAI_API_KEY=...
OPENAI_EMBED_MODEL=text-embedding-3-small
```

Deploy: `python orchestrator.py deploy --provider local --scope nonkube`

## Skylark search lane

```bash
EMBEDDING_ACTIVE_PROFILE=skylark_2048
ARK_API_KEY=...
ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3
ARK_EMBEDDING_MODEL_ID=skylark-embedding-vision-251215
```

`EMBEDDING_ACTIVE_PROFILE` selects **which column semantic search reads**. Storage populates **both** columns when credentials exist (CRUD + sync).

## Chat inference (orthogonal to search lane)

Default Claude chat (local Anthropic API):

```bash
LLM_INFERENCE_PROVIDER=claude   # default when unset
CLAUDE_API_KEY=...
CLAUDE_MODEL=claude-haiku-4-5
```

ModelArk chat (BytePlus):

```bash
LLM_INFERENCE_PROVIDER=modelark
ARK_API_KEY=...
ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3
ARK_CHAT_MODEL_ID=seed-2-0-lite-260228
```

You can use `EMBEDDING_ACTIVE_PROFILE=skylark_2048` for search while keeping `LLM_INFERENCE_PROVIDER=claude`, or switch both to ModelArk.

## Bootstrap / refresh vectors (from DB, not CSV profile replay)

```bash
# CSV scalars + dual-profile sync
python core_app/backend/etl/load_openai_embeddings_to_pgvector.py --sync-embeddings

# Fill missing profile columns for all DB rows (e.g. API-added F900)
PYTHONPATH=core_app python tools/cloud_shared/embed/sync_embeddings_cli.py --all --missing-only
```

## Verify

```bash
PYTHONPATH=core_app python tools/cloud_shared/verify/verify_embedding_profile.py
PYTHONPATH=core_app python tools/byteplus/standalone/verify_modelark.py
```

See [BYTEPLUS_AWS_GCP_REFERENCE.md](BYTEPLUS_AWS_GCP_REFERENCE.md).
