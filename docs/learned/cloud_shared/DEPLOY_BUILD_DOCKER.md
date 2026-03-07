# Deploy, Build & Docker: Consolidated Guide

Merged from BUILD_CONTENT_SKIP, DEPLOYMENT_OPTIMIZATION_LEARNED, and DOCKER_LEARNED. Covers content-based build skip, deployment optimizations, and Docker image flow.

---

## 1. Content-Based Build Skip

Deploy skips the Docker build when the build context (source + Dockerfile) hasn't changed. Saves ~40s–95s on re-deploys where only Terraform or config changed.

### How It Works

1. **Before build:** Compute hash of `core_app/` (excludes `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `*.pyc`). Includes Dockerfile path so app vs spark get different hashes.
2. **Compare:** Fetch stored hash from S3 (AWS) or GCS (GCP).
3. **Skip or build:** If both app and spark hashes match → skip build, use `repo:latest`. Otherwise → build and push.

**Why not Git SHA?** Git SHA only reflects committed state. Uncommitted changes would not change the hash; we'd deploy stale code. Content hashing captures any change.

### Storage

- **AWS:** `s3://{artifacts_bucket}/build-metadata/{env}/app-build-hash.json` (and spark). Hash is global per env, not per region.
- **GCP:** GCS equivalent via `tools.cloud_shared.docker.build_context_hash`.
- **Format:** `{"hash": "<24-char-hex>", "tag": "<image-tag>"}`

### Flags

| Flag | Effect |
|------|--------|
| (none) | Content-based skip when hash matches. Build on first deploy or when code changed. |
| `--skip-build` | Always skip build; use `repo:latest`. No hash check. |
| `--force-build` | Bypass content-based skip; always build. Use when code changed or you want a fresh image. |

### Multi-Region Push Without Rebuild

When deploying to a second region with content-skip (or `--skip-build`), target ECR may be empty → `ImageNotFoundException`. **Solution:** Images use regionless names; when content-skip and target ECR empty, run `--push-only` to tag local canonical images and push. No rebuild.

---

## 2. Deployment Optimizations (Implemented)

| Optimization | Typical savings | When it applies |
|--------------|-----------------|-----------------|
| **VPC tag lifecycle** | ~30–60 s | `lifecycle { ignore_changes = [tags] }` on subnets; avoids durable apply touching kube's tags |
| **Single kube apply** | ~1–5 min | `_try_get_lb_hostname` before first apply; skip second apply when hostname known |
| **Skip import + apply** | ~2–8 min per stack | `plan_shows_no_changes()` before import; skip when plan clean |
| **Content-based build skip** | ~3–10 min | Hash matches → skip Docker build and push |

**Rough total for clean full-scope re-deploy:** ~5–20 minutes saved.

### VPC Tag Drift (Durable vs Kube)

**Why Kube adds tags:** `kubernetes.io/role/elb` and `kubernetes.io/cluster/<cluster_name>` enable LB placement in public subnets. Without them → NLB in private subnets → CloudFront 502. See [KUBE_LB.md](KUBE_LB.md).

**Fix:** `lifecycle { ignore_changes = [tags] }` on subnet resources in `infra_terraform/modules/aws/primitives/vpc/main.tf`.

---

## 3. Docker Images: Concepts & Flow

### Image vs Compound Tag

| Concept | What It Is | Example |
|---------|------------|---------|
| **Image** | Content-addressable object (layers + filesystem), identified by Image ID | `534e52bc703a` |
| **Compound tag** | Full `name:tag` reference pointing to an image | `fru-api-img-dev:latest` |

**Canonical compound tag:** Without registry URL (e.g. `fru-api-img-dev:latest`). Our single local reference; reused when pushing to any region.

### Our Two Images

| Image | Repo Name | Purpose |
|-------|-----------|---------|
| **App** | `fru-api-img-dev` | FastAPI backend |
| **Spark** | `fru-spark-img-dev` | Analytics / Spark jobs |

**Regionless names:** Same repo name in all regions; enables push-only across regions without rebuild.

### Build & Push Flow

1. Build with local compound tags (`fru-api-img-dev:latest`, `fru-spark-img-dev:latest`).
2. Tag for target registry: `docker tag fru-api-img-dev:latest {ecr_url}/fru-api-img-dev:latest`.
3. Push to ECR/Artifact Registry.
4. Remove ECR compound tags locally; keep canonical names for push-only to other regions.

### Deploy Scenarios

| Scenario | Build? | Push? | Notes |
|----------|:------:|:-----:|-------|
| First deploy to region | Yes | Yes | No stored hash or registry empty |
| Same region, no code change | No | No | Content-skip; Phase 8 skipped |
| Different region, no code change | No | Push-only | Content-skip; target registry empty |
| Code changed | Yes | Yes | Hash mismatch |

### ECR Compound Tag Cleanup

After push, remove ECR registry compound tags locally (`docker rmi ecr.../fru-api-img-dev:latest`). Keep canonical compound tags. Use `--skip-untag-ecr` to keep ECR tags for debugging.

---

## 4. Implementation References

| Location | Purpose |
|----------|---------|
| `tools/cloud_shared/docker/build_context_hash.py` | `compute_build_context_hash()`; storage is provider-specific (S3 vs GCS) |
| `tools/aws/scope_shared/deploy/build_context_hash.py` | AWS wrapper for S3 |
| `tools/aws/deploy.py` | Content-skip check; `_maybe_push_only_for_region` |
| `tools/aws/scope_shared/deploy/build_and_push_images.py` | Build, push, store hash after success |
| `tools/gcp/scope_shared/deploy/build_and_push_images.py` | GCP equivalent with GCS |

---

## 5. Quick Reference

| Scenario | Result |
|----------|--------|
| Deploy same region twice, no code change | No build, no push; Phase 8 skipped |
| Deploy new region, no code change | Push-only; no rebuild |
| After push | ECR compound tags removed locally; canonical names kept |
| Uncommitted changes | Hash changes → build runs |
