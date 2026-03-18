# Refactor Plan: Image Tag Handling (Cross-Scope, Cross-Provider, DRY)

**Last updated:** 2026-03-16

## Goals

1. **Tag sourcing:** Use `APP_IMAGE_TAG` when set; else resolve from registry (what `latest` points to). Never use `latest` for deploy.
2. **Registry empty:** If registry has no images, require build or fail before kube/nonkube apply.
3. **Unify:** Single env var `APP_IMAGE_TAG`; remove `CONTAINER_IMAGE_TAGS`.
4. **DRY:** Shared resolver and image-URI helpers; consistent interface across AWS, GCP, scopes.

### Centralization Rationale

**Deploy sets only `APP_IMAGE_TAG`.** Scope deployers call `get_deploy_image_uris(provider, env, region)` when they need full URIs. Benefits:
- **Single place for URI building:** Resolver owns all logic; no `APP_IMAGE_FULL` / `SPARK_IMAGE_FULL` env vars.
- **Fewer env vars:** One (`APP_IMAGE_TAG`) instead of three.
- **Provider-agnostic:** Same pattern for AWS, GCP; resolver handles provider-specific repo URLs (tofu outputs / resource_names).

---

## Scope × Provider Matrix

| Provider | Scope   | Current image source                         | After refactor                    |
|----------|---------|----------------------------------------------|-----------------------------------|
| AWS      | kube    | deploy passes `app_image_full` to deploy_kube  | deploy sets `APP_IMAGE_TAG`; deploy_kube calls `get_deploy_image_uris()` |
| AWS      | nonkube | deploy passes `app_image_full` to deploy_nonkube | Same pattern |
| GCP      | kube    | deploy_kube reads `APP_IMAGE_TAG` + builds URI | Same pattern |
| GCP      | nonkube | deploy_nonkube builds from `TF_VAR_*` / default | Same pattern |
| Local    | kube    | `fru-api:local`, `CONTAINER_IMAGE_TAGS=""`   | `APP_IMAGE_TAG=local`             |
| Local    | nonkube | `fru-api:local` via compose                  | No change (no registry)           |

---

## Phase 1: Shared Module `tools/cloud_shared/deploy_image_resolver.py`

**Purpose:** Single place for tag resolution and image URI construction. Provider-agnostic API.

### 1.1 Functions

```python
# Resolve tag: env override, or query registry for what "latest" points to
def resolve_app_tag(provider: str, env: str, region: str, app_image_url: str) -> str
def resolve_spark_tag(provider: str, env: str, region: str, spark_image_url: str) -> str
# For simplicity: resolve_spark_tag = resolve_app_tag (spark uses same tag as app)

# Check registry has required images (app, spark, kube-proxy for GCP)
def registry_has_required_images(provider: str, env: str, region: str) -> bool

# Build full image URIs from repo base + tag (uses APP_IMAGE_TAG or resolve)
# Fetches repo URLs from provider-specific sources (tofu outputs, resource_names)
def get_deploy_image_uris(provider: str, env: str, region: str) -> tuple[str, str]
# Returns (app_image_full, spark_image_full). Called by scope deployers, not deploy.
```

### 1.2 Provider-specific helpers (private)

Tag lookup lives in `image_registry_tags.get_image_tags`; resolver delegates to it. **Phase 8 supersedes GCP approach below.**

- **GCP:** See Phase 8. Single REST path (Artifact Registry v1 API); digest-based. No gcloud.
- **AWS:** `describe_images(imageIds=[{imageTag}])` returns tags for that image in one call. Already per-digest.
- **Local:** `docker image inspect` returns `RepoTags` for that image. Already per-image.

### 1.3 DRY consolidation

- Tag lookup: delegate to `image_registry_tags.get_image_tags` (single source; see Module responsibilities).
- Move `_gcp_artifact_registry_has_image` logic into resolver (or call from resolver).
- `decide_build_skip` already uses `registry_has_images` callback; keep that, but `registry_has_required_images` can be the shared implementation.

---

## Phase 2: Unify to `APP_IMAGE_TAG` (Remove `CONTAINER_IMAGE_TAGS`)

### 2.1 Backend

| File | Change |
|------|--------|
| `core_app/backend/api/app.py` | `/version`: prefer `APP_IMAGE_TAGS` if set; else call `get_image_tags(CONTAINER_IMAGE, provider, region)` when registry available; else `[tag]` from `CONTAINER_IMAGE`. No `"latest"` default; use `"unknown"` if empty. |

### 2.2 K8s template (shared: AWS, GCP, Local)

| File | Change |
|------|--------|
| `api-deployment.yaml.j2` | Replace `CONTAINER_IMAGE_TAGS` with `APP_IMAGE_TAG`. |

### 2.3 Terraform (AWS + GCP nonkube)

| File | Change |
|------|--------|
| `infra_terraform/live_deploy/aws/nonkube/main.tf` | `APP_IMAGE_TAG = var.app_image_tag` (rename var) |
| `infra_terraform/live_deploy/aws/nonkube/variables.tf` | Rename `app_image_tags` → `app_image_tag` (string) |
| `infra_terraform/live_deploy/gcp/nonkube/main.tf` | Same |
| `infra_terraform/live_deploy/gcp/nonkube/variables.tf` | Same |
| `tools/aws/scope_shared/core/terra_var_handling.py` | MAP already has `APP_IMAGE_TAG` → `app_image_tag`; ensure get_base_vars sets it when building TF_VAR_app_image (uses tag + repo). |

### 2.4 Remove

- `get_container_image_tags()` from `image_tag.py`.
- All `CONTAINER_IMAGE_TAGS` references.

---

## Phase 3: Deploy Orchestration – Unified Flow

### 3.1 Principle (Cleaner Centralization)

**Deploy sets only `APP_IMAGE_TAG`.** Scope deployers (kube, nonkube) call `get_deploy_image_uris(provider, env, region)` when they need full URIs. The resolver is the single place that builds full URIs; deploy does not set `APP_IMAGE_FULL` or `SPARK_IMAGE_FULL`. One env var, one source of truth.

### 3.2 GCP `deploy.py`

1. **Build runs:** Set `APP_IMAGE_TAG = version_tag` (from `generate_image_tag`).
2. **Build skipped (content hash):** Call `resolve_app_tag("gcp", ...)`; set `APP_IMAGE_TAG`.
3. **`--skip-build`:**  
   - Call `registry_has_required_images("gcp", ...)`. If false → `sys.exit(1)` with clear message.  
   - Call `resolve_app_tag(...)`; set `APP_IMAGE_TAG`.
4. **Remove:** No Phase 8.5; deploy does not call `get_deploy_image_uris`. Scope deployers do.
5. **Add push-only for empty registry:** When build skipped (content hash or `--skip-build`), call `push_only_for_registry_absence` (mirror AWS). If push fails → fail deploy.
6. Remove all `CONTAINER_IMAGE_TAGS` handling.

### 3.3 AWS `deploy.py`

1. **Build runs:** Set `APP_IMAGE_TAG = version_tag`.
2. **Content-skip / `--skip-build`:**  
   - Keep `_push_only_for_ecr_absence`.  
   - Use `resolve_app_tag("aws", ...)` instead of `repo:latest`; set `APP_IMAGE_TAG`.
3. **Remove:** No Phase 9 image-URI computation; scope deployers call `get_deploy_image_uris`.
4. **Change deploy invocation:** `run_deploy_nonkube(env, region, snd, args, stats)` and `run_deploy_kube(env, region, snd, args, stats)` — remove `app_image_full`, `spark_image_full` args.
5. Remove `CONTAINER_IMAGE_TAGS`.

### 3.4 Scope deployers (AWS + GCP, unified)

- **`run_deploy_nonkube`:** At start, call `app_full, spark_full = get_deploy_image_uris(provider, env, region)`. Use for `-var=app_image=`, `-var=spark_image=`. Use `APP_IMAGE_TAG` from env for `app_image_tag`.
- **`run_deploy_kube`:** Same. Call `get_deploy_image_uris()` at start; pass `app_full`, `spark_full` to kube_apply.

---

## Phase 4: Consumers – Call Resolver

### 4.1 Kube (AWS, GCP)

| File | Change |
|------|--------|
| `tools/aws/kube/deploy_kube.py` | At start, call `app_full, spark_full = get_deploy_image_uris("aws", env, region)`. Pass to kube_apply. Remove `app_image_full`, `spark_image_full` from signature. |
| `tools/gcp/kube/deploy_kube.py` | Same with `"gcp"`. |
| `tools/aws/kube/kube_apply.py` | Receive `--app-image`, `--spark-image` from deploy_kube. Pass `APP_IMAGE_TAG` (from env) to template. |
| `tools/gcp/kube/kube_apply.py` | Same. |

### 4.2 Nonkube (AWS, GCP)

| File | Change |
|------|--------|
| `tools/aws/nonkube/deploy_nonkube.py` | At start, call `get_deploy_image_uris("aws", env, region)`. Use for `-var=app_image=`, `-var=spark_image=`. Use `APP_IMAGE_TAG` for `app_image_tag`. Remove image args from signature. |
| `tools/gcp/nonkube/deploy_nonkube.py` | Same with `"gcp"`. Remove `TF_VAR_app_image` fallback. |

### 4.3 Local

| File | Change |
|------|--------|
| `tools/local/kube/kube_apply.py` | Pass `APP_IMAGE_TAG` = `"local"` (derived from `args.app_image` or default). |
| `api-deployment.yaml.j2` | Already supports `APP_IMAGE_TAG` (after Phase 2). |

### 4.4 Build scripts

- `build_and_push_images.py` (GCP, AWS): Keep `APP_IMAGE_TAG` as input only. No tag generation.

### 4.5 Teardown

- Use `APP_IMAGE_TAG` when available; else resolve from registry for cleanup.

### 4.6 Standalone scripts

- `fix_kube_db_credentials.py`, etc.: Use `resolve_app_tag()` or require `APP_IMAGE_TAG`.

---

## Phase 5: Terraform Variable Rename

- `app_image_tags` → `app_image_tag` (singular, string).
- Update all `-var=app_image_tags=` → `-var=app_image_tag=`.

---

## Phase 6: SPARK_IMAGE_TAG and Push Strategy

### Push strategy (app and spark)

- **Push both tags:** Each image gets `version_tag` (e.g. `fru_dev_20260317_...`) AND `latest` — same digest, two tags.
- **Why:** `latest` = convenience for search/pull; concrete tag = reproducible deploy + `/version` display.
- **Deploy uses concrete tag** (never `latest`) so we know exactly what is running.

### SPARK_IMAGE_TAG = APP_IMAGE_TAG

- **Option A:** Use same tag as app. `resolve_spark_tag` = `resolve_app_tag`. Simpler.
- **Option B:** Keep `SPARK_IMAGE_TAG` for explicit override. Default to `APP_IMAGE_TAG`.
- **Recommendation:** Option A.

### Implementation checklist (Phase 6)

| Location | Change |
|----------|--------|
| `tools/gcp/deploy.py` (build phase) | Set `SPARK_IMAGE_TAG = APP_IMAGE_TAG` before invoking build (not `"latest"`). |
| `tools/aws/deploy.py` (build phase) | Same: ensure `SPARK_IMAGE_TAG` defaults to `APP_IMAGE_TAG` when unset. |
| `build_and_push_images.py` (GCP, AWS) | Already pushes both `version_tag` and `latest` when tag ≠ "latest". No change. |

---

## Phase 7: Cleanup and Docs

- Update `WAR_STORIES_CLOUD_SHARED.md` §21.
- Update `DEPLOY_BUILD_DOCKER.md`, `BACKEND_SCALING_NONKUBE_MULTI_CLOUD.md`.
- Remove `get_container_image_tags` from `image_tag.py`.

---

## Execution Order

1. Phase 1: Create `deploy_image_resolver.py`. → **Run Stage 1 tests**
2. Phase 2: Unify to `APP_IMAGE_TAG` (backend, template, Terraform). → **Run Stage 2 tests**
3. Phase 3: Deploy orchestration (GCP, AWS).
4. Phase 4: Consumers (kube_apply, deploy_kube, deploy_nonkube, local). → **Run Stage 3 tests**
5. Phase 5: Terraform var rename. → **Run Stage 4 tests**
6. Phase 6: SPARK_IMAGE_TAG (if needed).
7. Phase 7: Docs and cleanup. → **Run Stage 5 (E2E) tests**
8. Phase 8: Digest-based tag filtering (`image_registry_tags.py`). → **Run Stage 8 tests**
9. Phase 9: Timezone consistency (`image_tag.py`). → **Run Stage 9 tests**

---

## Interface Summary (Post-Refactor)

| Env var | Set by | Used by |
|---------|--------|---------|
| `APP_IMAGE_TAG` | Deploy (build or resolver) | Backend `/version`, Terraform `app_image_tag`, teardown, resolver (when building URIs) |

**Single source of truth:** Deploy sets only `APP_IMAGE_TAG`. Scope deployers call `get_deploy_image_uris(provider, env, region)` to obtain full URIs; the resolver is the single place that builds them.

### Module responsibilities (DRY)

| Module | Responsibility | Used by |
|--------|----------------|--------|
| `image_registry_tags` | Tag lookup: `get_image_tags(container_image, provider, region)` → tags for that image's digest | `deploy_image_resolver`, `app.py` `/version` |
| `deploy_image_resolver` | Tag resolution (env override + registry), URI building: `get_deploy_image_uris`, `resolve_app_tag` | Deploy scripts, scope deployers |
| `image_tag` | Tag generation: `generate_image_tag()` for build | Deploy (build phase) |

No duplication: tag lookup in one place; resolution/URI building in another; generation in a third.

---

## Flow Diagram (Post-Refactor)

```
Deploy (AWS or GCP)
├── Build or skip
│   ├── Build runs → APP_IMAGE_TAG = generate_image_tag()
│   ├── Build skipped → APP_IMAGE_TAG = resolve_app_tag()
│   └── --skip-build → registry check → fail if empty; APP_IMAGE_TAG = resolve_app_tag()
└── Scope deploy (kube / nonkube)
    ├── run_deploy_kube: get_deploy_image_uris(provider, env, region) → (app_full, spark_full) → kube_apply
    └── run_deploy_nonkube: get_deploy_image_uris(...) → Terraform -var=app_image=, spark_image=; APP_IMAGE_TAG → app_image_tag
```

---

## Risks

| Risk | Mitigation |
|------|-------------|
| AWS/GCP API differences | Provider-specific helpers in `image_registry_tags`; one path per provider. |
| Local provider | Resolver returns local images or no-op. |
| Terraform var rename | Update all `-var=` and variable references. |
| GCP v1 API parsing | Shared `_parse_gcp_repo_base` for `repo_base` → project/location/repository. |

---

## Phase 8: Digest-Based Tag Filtering (Build Display)

**Goal:** Show only tags for the current running image (its digest), e.g. `Build: ['latest', fru_dev_20260317_0112676_dirty_20260316_163943]` — typically 1–2 tags, not all repo tags.

### 8.1 Callers and Semantics

| Caller | Purpose |
|--------|---------|
| `app.py` `/version` | UI: show tags for the running container's image |
| `deploy_image_resolver._resolve_version_tag_from_registry` | Deploy: when `--skip-build`, get a concrete version tag for the image being deployed |

Both need tags for the **specific digest** of the given image reference. `get_image_tags` should return only tags that point to that digest.

### 8.2 Provider Status

| Provider | Current behavior | Change needed |
|----------|------------------|---------------|
| **GCP** | REST: OCI `tags/list` returns all repo tags. gcloud: per-image already correct. | Consolidate to **single REST path**; remove gcloud. Use GCP Artifact Registry v1 API for digest-based lookup. |
| **AWS** | `describe_images(imageIds=[{imageTag}])` returns tags for that image. | No change. |
| **Local** | `docker image inspect` returns `RepoTags` for that image. | No change. |

**Rationale for GCP consolidation:** REST uses ADC (Application Default Credentials), which works in both container (Cloud Run/GKE) and deploy host. `gcloud` is redundant; one path per provider.

### 8.3 Implementation Plan (DRY)

**Single source for tag lookup:** `image_registry_tags.get_image_tags`. Both deploy and `/version` use it.

**Per-provider (no shared digest abstraction):** AWS and Local already return per-image tags in one call. Only GCP needs digest-based logic.

1. **GCP only** — replace `_gcp_tags_via_rest` and remove `_gcp_tags_via_gcloud`:
   - Add private `_gcp_resolve_digest(repo_base, tag)` via OCI `GET /v2/{name}/manifests/{tag}` → `Docker-Content-Digest` header.
   - Add private `_parse_gcp_repo_base(repo_base)` → `(project, location, repository)` for v1 API.
   - New `_gcp_get_tags`: resolve digest → call v1 `dockerImages.list` → find image by digest → return its `tags`.
   - Use ADC for auth (works in container and deploy host).

2. **AWS, Local:** No changes. `describe_images` and `docker inspect` already return tags for the given image.

3. **`get_image_tags` semantics:** GCP path returns digest-filtered tags; AWS/Local unchanged. On failure, fall back to `[tag]` from `container_image`.

4. **Callers** (`deploy_image_resolver`, `app.py`): No changes.

---

## Phase 9: Timezone Consistency in Image Tags

**Goal:** Align `commit_date` and `timestamp` to the same timezone; include timezone in the tag, in letters.

### 9.1 Root Cause

- **`commit_date`:** From `git log --format=%cd --date=format:%Y%m%d` → uses git's default timezone (author/committer local).
- **`timestamp`:** From `datetime.utcnow()` → UTC.

Mixing timezones causes `commit_date` to appear "after" `timestamp` when author is ahead of UTC.

### 9.2 Desired Behavior

- Use the **same timezone** for both `commit_date` and `timestamp`.
- Use the timezone that `commit_date` uses (from git).
- Include the timezone in the tag, in letters (or clear abbreviation).

### 9.3 Approach

1. **Get timezone from git:** `git log -1 --format=%ci HEAD` → e.g. `"2026-03-17 01:39:43 +0800"`. Parse the offset (e.g. `+0800` → `timedelta(hours=8)`).

2. **Use that timezone for `timestamp`:** Build `datetime.now(timezone(parsed_offset))` and format as `%Y%m%d_%H%M%S`.

3. **Include timezone in the tag:**
   - For offset `+0000`: use `"UTC"`.
   - For other offsets: use the offset string (e.g. `+0800`, `-0500`) or short form like `UTC+8` / `UTC-5`.
   - Resulting format: `fru_{env}_{commit_date}_{sha}_dirty_{timestamp}_{tz}`  
     - Example: `fru_dev_20260317_0112676_dirty_20260317_013943_p0800` (Docker-safe: p=positive, m=negative)  
     - Or: `fru_dev_20260317_0112676_dirty_20260317_013943_UTC`

4. **Implementation details:**
   - `%ci` uses committer's timezone (or `%ai` for author).

   - If parsing fails (e.g. not in git), fall back to `datetime.utcnow()` and `"UTC"`.

   - Python `zoneinfo` (3.9+) can map offsets to abbreviations (e.g. `PST`, `PDT`) when needed; offset strings like `+0800` are unambiguous and portable.

5. **Files to change:** `tools/cloud_shared/image_tag.py` only.

6. **Tag format:**
   - Dirty: `fru_{env}_{commit_date}_{sha}_dirty_{timestamp}_{tz}`
   - Clean: unchanged (no timestamp).

---

## Test Steps (Staged by Phase)

Runnable checks to validate each phase. Run after completing each phase.

### Stage 1: After Phase 1

| Step | Command / check |
|------|-----------------|
| 1.1 | `python -c "from tools.cloud_shared.deploy_image_resolver import get_deploy_image_uris; print(get_deploy_image_uris('gcp','dev','us-central1'))"` with `APP_IMAGE_TAG` set → prints `(repo/app:tag, repo/spark:tag)`. |
| 1.2 | Same for `"aws"` → prints ECR URIs. |
| 1.3 | Same for `"local"` → prints `(fru-api:local, fru-spark:local)`. |

### Stage 2: After Phase 2

| Step | Command / check |
|------|-----------------|
| 2.1 | Start API locally with `APP_IMAGE_TAG=test`; `curl localhost:5001/version` → `version` includes `test`. |
| 2.2 | `tofu plan` for nonkube with `-var=app_image_tag=test` → no variable errors. |

### Stage 3: After Phase 3 + 4

| Step | Command / check |
|------|-----------------|
| 3.1 | `python tools/gcp/deploy.py --scope nonkube --skip-build --apply` (registry populated) → succeeds. |
| 3.2 | `python tools/gcp/deploy.py --scope nonkube --skip-build` (registry empty) → fails with clear message. |
| 3.3 | Full deploy (build runs) → `APP_IMAGE_TAG` set; kube/nonkube use correct images. |

### Stage 4: After Phase 5

| Step | Command / check |
|------|-----------------|
| 4.1 | `tofu plan` for nonkube with `-var=app_image_tag=...` → plan succeeds. |
| 4.2 | Full nonkube deploy → Cloud Run / ECS has `APP_IMAGE_TAG` env. |

### Stage 5: End-to-end

| Step | Command / check |
|------|-----------------|
| 5.1 | Full GCP deploy (scope=all) → API pods run; `/version` returns version tag. |
| 5.2 | GCP deploy with `--skip-build` (registry has images) → same. |
| 5.3 | Local kube deploy → `APP_IMAGE_TAG=local` in pod; `/version` works. |

### Stage 8: After Phase 8 (Digest-based tag filtering)

| Step | Command / check |
|------|-----------------|
| 8.1 | `get_image_tags(repo:latest, "gcp", region)` → returns only tags for that digest (1–2 tags), not all repo tags. |
| 8.2 | `/version` in deployed API → `version` array has 1–2 tags (e.g. `['latest', fru_dev_...]`). |
| 8.3 | Deploy with `--skip-build` → `_resolve_version_tag_from_registry` returns correct version tag for latest image. |

### Stage 9: After Phase 9 (Timezone consistency)

| Step | Command / check |
|------|-----------------|
| 9.1 | `generate_image_tag()` in dirty repo (author in non-UTC tz) → `commit_date` and `timestamp` same day or timestamp later. |
| 9.2 | Dirty tag format includes timezone suffix, e.g. `..._dirty_20260317_013943_+0800` or `..._UTC`. |
