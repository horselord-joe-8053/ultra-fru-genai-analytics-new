# Env Vars Not Aligned with Naming Convention

**Convention:** `<proj_prefix>-<component>-<env>...` (or path-style `/{proj}/{component}/{env}/{region}`)  
**Reference:** `docs/STEP_LARGE_REFACTOR_RENAMING.md`  
**Refactor plan:** `docs/ENV_NAMING_REFACTOR_IMPACT.md` (phased migration steps)

The following env vars still hold **full names** or **legacy values** instead of component-only values:

| Env Var | Current Value | Issue | Recommended Refactor |
|---------|---------------|-------|----------------------|
| `CLOUDWATCH_LOG_GROUP` | `/fru/dev/spark` | Full path with proj+env baked in | Deprecate; use `CLOUDWATCH_LOG_GROUP_SPARK=cloud-log-group-spark` and build path `/{PROJ_PREFIX}/{component}/{env}/{region}` |
| `EKS_CLUSTER_NAME` | `fru-dev-eks` | Full name | Deprecate; use `EKS_CLUSTER_COMPONENT=eks` (already exists); code uses as legacy fallback in `_component()` |
| `ECS_CLUSTER_NAME` | `fru-dev-ecs` | Full name | Deprecate; use `ECS_CLUSTER_COMPONENT=ecs` (already exists); code uses as legacy fallback |
| `K8S_NAMESPACE` | `fru-kube` | Full name `{proj}-{component}` | Add `K8S_NAMESPACE_COMPONENT=kube`; build `{PROJ_PREFIX}-{component}` at runtime |
| `PGDATABASE` | `fru_db` | Full name `{proj}_db` | Add `PG_DATABASE_COMPONENT=db`; build `{PROJ_PREFIX}_{component}` at runtime |
| `DELTA_TABLE_PATH` | `data/delta/fru_sales` (local) | Contains table name `fru_sales` | Add `DELTA_TABLE_COMPONENT=fru_sales` or `DELTA_TABLE_COMPONENT=sales`; path = `{bucket}/delta/{proj}_{component}` |

**Out of scope (per STEP_LARGE_REFACTOR_RENAMING):**
- `IMAGE_PREFIX` — Local Docker tag prefix; not a cloud resource name.
- `VPC_CIDR`, `LOG_LEVEL`, credentials, etc. — Not resource names.

**Already aligned (component-only):**
- `S3_DELTA_COMPONENT`, `ECR_APP_COMPONENT`, `EKS_CLUSTER_COMPONENT`, `ECS_CLUSTER_COMPONENT`
- `GCS_DELTA_COMPONENT`, `ARTIFACT_REGISTRY_APP_COMPONENT`, `SPARK_JOB_COMPONENT`, etc.
