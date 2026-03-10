# TODO: Multi-LLM Config Refactor

## Overview

Refactor LLM configuration from `.env`-centric to config-file-driven, so each cloud backend (aws, gcp, local) can freely choose which LLM providers (Google, OpenAI, Anthropic, DeepSeek) to use, as long as the model and a usable API key are provided.

## Goals

1. **Decouple LLM credentials from cloud provider** – credentials and model lists live in a dedicated LLM config.
2. **Per-cloud LLM selection** – each cloud backend specifies which LLM to use for backend (query/SQL) and vectorization (embeddings).
3. **Clean up .env** – move LLM-related variables to config files; `.env` keeps only secrets that must stay out of version control (or reference config paths).

---

## Proposed Config Structure

### 1. `config/llm/llm_cred_config.json`

Single source of truth for LLM provider credentials and allowed models. Values can be placeholders; real secrets loaded from env or secret manager at runtime.

```json
{
  "anthropic": {
    "api_key_env": "CLAUDE_API_KEY",
    "models": [
      "claude-3-5-haiku-20241022",
      "claude-3-5-sonnet-20241022",
      "claude-3-opus-20240229"
    ]
  },
  "google": {
    "api_key_env": "GOOGLE_AI_API_KEY",
    "models": [
      "gemini-2.5-flash",
      "gemini-2.5-pro",
      "gemini-1.5-flash"
    ]
  },
  "openai": {
    "api_key_env": "OPENAI_API_KEY",
    "models": [
      "gpt-4o",
      "gpt-4o-mini",
      "gpt-4-turbo"
    ]
  },
  "deepseek": {
    "api_key_env": "DEEPSEEK_API_KEY",
    "models": [
      "deepseek-chat",
      "deepseek-coder"
    ]
  }
}
```

**Notes:**
- `api_key_env`: env var name to read the API key from (or from secret manager in cloud).
- `models`: list of model IDs this provider supports; used for validation and defaults.
- File is versioned; actual keys stay in `.env` or cloud secrets.

---

### 2. `config/cloud/cloud_llm_config.json`

Per-cloud-provider LLM selection. Keys are cloud provider names; values specify which LLM provider and model to use for backend and vectorization.

```json
{
  "aws": {
    "backend_llm_provider": "anthropic",
    "backend_llm_model": "claude-3-5-haiku-20241022",
    "vectorization_llm_provider": "openai",
    "vectorization_llm_model": "text-embedding-3-small"
  },
  "gcp": {
    "backend_llm_provider": "anthropic",
    "backend_llm_model": "claude-3-5-haiku-20241022",
    "vectorization_llm_provider": "openai",
    "vectorization_llm_model": "text-embedding-3-small"
  },
  "local": {
    "backend_llm_provider": "anthropic",
    "backend_llm_model": "claude-3-5-haiku-20241022",
    "vectorization_llm_provider": "openai",
    "vectorization_llm_model": "text-embedding-3-small"
  }
}
```

**Notes:**
- `backend_llm_*`: used for query agent, SQL generation, etc.
- `vectorization_llm_*`: used for embeddings (currently OpenAI; could add Cohere, Voyage, etc.).
- Environment override: e.g. `FRU_ENV=prod` could load `cloud_llm_config.prod.json` or a merged config.

---

## Variables to Move from .env

| Current .env Variable | Destination | Notes |
|-----------------------|-------------|-------|
| `CLAUDE_API_KEY` | Secret only (env / Secret Manager) | Stays in .env for local; cloud uses secret manager |
| `GOOGLE_AI_API_KEY` | Secret only | Same |
| `OPENAI_API_KEY` | Secret only | Same |
| `GCP_LLM_PROVIDER` | `cloud_llm_config.json` → `backend_llm_provider` | Per-cloud |
| `LLM_PROVIDER` | Alias; deprecate in favor of config | |
| `CLAUDE_MODEL` | `cloud_llm_config.json` → `backend_llm_model` | |
| `GOOGLE_MODEL` / `GEMINI_MODEL` | `cloud_llm_config.json` → `backend_llm_model` | |
| `OPENAI_EMBED_MODEL` | `cloud_llm_config.json` → `vectorization_llm_model` | |
| `AWS_BEDROCK_MODEL_ID` | AWS-specific; could stay or map to `backend_llm_model` | Bedrock uses different model ID format |
| `AWS_BEDROCK_INFERENCE_PROFILE_ID` | AWS-specific | Keep in .env or Terraform vars |

**Remaining in .env:**
- API keys (or paths to secret files) – never in versioned config.
- Override flags if needed (e.g. `LLM_CONFIG_OVERRIDE=/path/to/custom.json`).

---

## Implementation Phases

### Phase 1: Add Config Files (No Behavior Change)
1. Create `config/llm/llm_cred_config.json` with current providers and models.
2. Create `config/cloud/cloud_llm_config.json` with aws, gcp, local entries.
3. Add `config/llm/llm_cred_config.example.json` and `cloud_llm_config.example.json` for docs.

### Phase 2: Config Loader
1. Add `core_app/backend/config/llm_config.py` (or `tools/cloud_shared/config/llm_config.py`):
   - `load_llm_cred_config()` → dict from `config/llm/llm_cred_config.json`
   - `load_cloud_llm_config()` → dict from `config/cloud/cloud_llm_config.json`
   - Support `LLM_CONFIG_DIR` / `CLOUD_LLM_CONFIG_PATH` env overrides.
2. Validate config on load (required keys, model in allowed list).

### Phase 3: Wire Backend to Config
1. **client_factory.py** / provider `get_llm_client()`:
   - Read `backend_llm_provider` and `backend_llm_model` from cloud config for current `CLOUD_PROVIDER`.
   - Resolve API key from `llm_cred_config[provider].api_key_env` → `os.environ`.
   - Instantiate correct client (LocalClaudeClient, GCPGeminiAPIClient, etc.) with model from config.
2. **Embeddings**: Read `vectorization_llm_provider` and `vectorization_llm_model`; currently OpenAI-only, extend if adding Cohere/Voyage.

### Phase 4: Terraform / Deploy
1. Deploy scripts read `cloud_llm_config.json` (or env overrides) to pass `llm_provider`, `claude_model`, etc. to Terraform.
2. Ensure `ensure_secrets` still populates API keys from `.env` into Secret Manager; config only selects which key to use.

### Phase 5: .env Cleanup
1. Remove or deprecate `GCP_LLM_PROVIDER`, `LLM_PROVIDER`, `CLAUDE_MODEL`, `GOOGLE_MODEL`, `GEMINI_MODEL`, `OPENAI_EMBED_MODEL` from .env (with fallback to env for backward compat during transition).
2. Update `.env.example` to document that LLM selection is in config; API keys remain in .env.

---

## Edge Cases

1. **AWS Bedrock**: Uses inference profile ID or model ID; format differs from Anthropic API. Keep Bedrock-specific vars in Terraform; config can map `backend_llm_provider=anthropic` → use Bedrock with configured model ID.
2. **Missing config**: Fall back to current env-based logic (e.g. `GCP_LLM_PROVIDER`, `CLAUDE_MODEL`) so existing deploys keep working.
3. **Multiple regions**: `cloud_llm_config` could support `aws.us-east-1`, `gcp.us-central1` overrides if needed later.

---

## Feasibility

- **Logic**: Sound. Separating credentials (who can we call) from selection (who do we use) is a standard pattern.
- **Feasibility**: High. Config files are additive; migration can be incremental with env fallbacks.
- **Risk**: Low if Phase 1–2 are done first with no behavior change; Phase 3 can be feature-flagged.

---

## Out of Scope (For Later)

- DeepSeek client implementation (config structure supports it; client code would be new).
- Per-endpoint model override (e.g. different model for `/query` vs `/query/stream`).
- Runtime config reload without restart.
