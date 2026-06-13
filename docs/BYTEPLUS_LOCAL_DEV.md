# BytePlus ModelArk — local development

## OpenAI profile (default)

```bash
EMBEDDING_ACTIVE_PROFILE=openai_1536
OPENAI_API_KEY=...
OPENAI_EMBED_MODEL=text-embedding-3-small
```

Deploy: `python orchestrator.py deploy --provider local --scope nonkube`

## Skylark / ModelArk profile

```bash
EMBEDDING_ACTIVE_PROFILE=skylark_2048
LLM_INFERENCE_PROVIDER=modelark
ARK_API_KEY=...
ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3
ARK_CHAT_MODEL_ID=<endpoint-id>
ARK_EMBEDDING_MODEL_ID=<embedding-endpoint-id>
```

Backfill the skylark column (migration eval only):

```bash
EMBEDDING_ACTIVE_PROFILE=skylark_2048 python core_app/backend/etl/load_openai_embeddings_to_pgvector.py
```

Verify:

```bash
PYTHONPATH=core_app python tools/cloud_shared/verify/verify_embedding_profile.py
PYTHONPATH=core_app python tools/byteplus/standalone/verify_modelark.py
```

See [BYTEPLUS_AWS_GCP_REFERENCE.md](BYTEPLUS_AWS_GCP_REFERENCE.md).
