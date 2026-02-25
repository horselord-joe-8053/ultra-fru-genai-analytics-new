# Content-Based Build Skip

Deploy can skip the Docker build step when the build context (source code + Dockerfile) hasn't changed. This saves ~40 seconds on re-deploys where only Terraform or config changed.

## How It Works

1. **Before build:** Deploy computes a hash of the build context (`core_app/` for both app and spark images, with different Dockerfile paths).
2. **Compare:** Fetches the stored hash from S3 (from the last successful build).
3. **Skip or build:** If both app and spark hashes match, skip build and use `repo:latest` from ECR. Otherwise, build and push.

## What Gets Hashed

- All files in `core_app/` that affect the image
- Excludes: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `*.pyc`
- Includes the Dockerfile path so app vs spark get different hashes

## Why Not Git SHA?

Git SHA only reflects **committed** state. Uncommitted changes (e.g. testing local edits) would not change the hash. We'd skip build and deploy stale code. Hashing file contents captures any change—committed or not.

## Storage

- **Location:** `s3://{artifacts_bucket}/build-metadata/{env}/app-build-hash.json` and `spark-build-hash.json`
- **Format:** `{"hash": "<24-char-hex>", "tag": "<image-tag>"}`
- **When written:** After each successful build and push (in `build_and_push_images.py`)

## Flags

| Flag | Effect |
|------|--------|
| (none) | Content-based skip when hash matches. Build on first deploy or when code changed. |
| `--skip-build` | Always skip build; use `repo:latest`. No hash check. |
| `--force-build` | Bypass content-based skip; always build. Use when you changed code or want a fresh image. |

## Implementation

- **`tools/aws/scope_shared/deploy/build_context_hash.py`** — `compute_build_context_hash()`, `get_stored_build_hash()`, `store_build_hash()`
- **`tools/aws/deploy.py`** — Content-based skip check before phase 7
- **`tools/aws/scope_shared/deploy/build_and_push_images.py`** — `--build-arg BUILD_CONTEXT_HASH`, store hash after push
- **Dockerfiles** — `ARG BUILD_CONTEXT_HASH` and `LABEL build_context_hash=${BUILD_CONTEXT_HASH}`

## Requirements

- `artifacts_bucket` output from nondurable stack (S3 bucket for build metadata)
- AWS credentials with S3 read/write on `artifacts_bucket`
