# Refactor Plan: Aurora + DB Wiring and Functionality Gap

> **Superseded by [FINAL_REFACTOR_PLAN.md](./FINAL_REFACTOR_PLAN.md)** – This content has been merged into the consolidated plan.

**Status**: Plan (implementation pending)  
**Created**: 2026-02-10  
**Purpose**: Close the gap between the new project and legacy for Aurora PostgreSQL (pgvector), DB setup, PG* env vars, and kube parity.

---

## 1. Executive Summary

The new project (`fru-genai-analytics-new`) currently lacks:

| Gap | Legacy | New (current) |
|-----|--------|---------------|
| **Aurora** | Aurora Serverless v2 in root_infrastructure | No Aurora; durable has VPC + Secrets only |
| **DB setup** | `setup-database.sh` → ensure-pgvector → init_schema → load_data | No schema, no init, no load flow |
| **PG* env vars** | PGHOST, PGDATABASE, PGUSER, PGPASSWORD from infra to ECS/EKS | ECS: PGPASSWORD only (secret); no PGHOST, PGDATABASE, PGUSER |
| **Kube parity** | Uses shared_nondurable for ECR, delta_bucket | Kube does not use shared_nondurable |
| **ETL** | `load_openai_embeddings_to_pgvector_rds_api.py` with DB_CLUSTER_ARN, DB_SECRET_ARN | ETL exists but no DB to load into; no env vars passed |

This document defines the wiring and implementation tasks to close these gaps.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         infra_terraform/live_deploy/aws/scope_shared/durable                       │
│  VPC + Aurora (pgvector) + Secrets (openai_api_key, db_password)              │
│  Outputs: vpc_id, subnets, aurora_endpoint, aurora_port, aurora_database_name│
│           aurora_security_group_id, db_cluster_arn, db_password_secret_arn   │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                    │
                    ▼                                    ▼
┌───────────────────────────────────┐    ┌───────────────────────────────────┐
│  infra_terraform/live_deploy/aws/scope_shared/nondurable │    │  DB Setup (tools/aws/setup_database) │
│  ECR, S3 (delta, artifacts)       │    │  ensure_pgvector → init_schema →    │
│  Outputs: ecr_app_url, ecr_spark_  │    │  load_data (RDS Data API)           │
│  url, delta_bucket                 │    │  Uses: durable outputs              │
└───────────────────────────────────┘    └───────────────────────────────────┘
                    │                                    │
                    ▼                                    ▼
┌───────────────────────────────────┐    ┌───────────────────────────────────┐
│  infra_terraform/live_deploy/aws/kube              │    │  infra_terraform/live_deploy/aws/nonkube           │
│  EKS + frontend                    │    │  ECS + ALB + frontend              │
│  Uses: durable + nondurable        │    │  Uses: durable + nondurable        │
│  PG* from durable                  │    │  PG* from durable                  │
└───────────────────────────────────┘    └───────────────────────────────────┘
```

---

## 3. Implementation Tasks

### 3.1 Aurora Module

**Path**: `infra_terraform/modules/aws/primitives/aurora/`

**Source**: Port from legacy `module_infra_basic/aws/terra/modules/aurora/`

**Files**:
- `main.tf` – aws_db_subnet_group, aws_security_group, aws_rds_cluster, aws_rds_cluster_instance
- `variables.tf` – vpc_id, private_subnet_ids, database_name, master_username, master_password, engine_version, instance_class, instance_count, min_capacity, max_capacity, tags, etc.
- `outputs.tf` – cluster_endpoint, cluster_port, database_name, security_group_id, cluster_arn

**Notes**:
- Aurora PostgreSQL with pgvector (extension installed via SQL after creation)
- Serverless v2 scaling configuration
- `enable_http_endpoint = true` for RDS Data API
- Master password: use `aws_secretsmanager_secret_version` data source to read from existing `db_password` secret, or `manage_master_user_password = true` with RDS-managed secret (preferred for new setups)

**Reference**: `fru-genai-analytics-legacy/module_infra_basic/aws/terra/modules/aurora/main.tf`

---

### 3.2 Durable Stack: Add Aurora

**Path**: `infra_terraform/live_deploy/aws/scope_shared/durable/main.tf`

**Changes**:
1. Add `module "aurora"` calling `infra_terraform/modules/aws/primitives/aurora`
2. Wire VPC outputs (private_subnet_ids, vpc_id) to Aurora module
3. Wire `db_password` from Secrets Manager:
   - Option A: Use `data "aws_secretsmanager_secret_version" "db_password"` and pass to Aurora
   - Option B: Use RDS `manage_master_user_password = true` and create RDS-managed secret (then output that ARN for ETL)
4. Add security group rule: Aurora SG allows ingress from ECS/EKS task SGs (deferred to ECS/EKS stacks via `aws_security_group_rule` with `source_security_group_id`)

**New outputs** (durable):
- `aurora_endpoint`
- `aurora_port`
- `aurora_database_name`
- `aurora_security_group_id`
- `db_cluster_arn` (for RDS Data API)
- `db_secret_arn` (for RDS Data API – either existing db_password_secret_arn or RDS-managed)

**Variables** (durable): Add `aurora_database_name`, `aurora_engine_version`, `aurora_instance_class`, etc. (or use defaults)

---

### 3.3 Schema and DB Setup Scripts

#### 3.3.1 Schema File

**Path**: `core_app/sql/schema_pgvector.sql`

**Action**: Copy from legacy `module_app_core/sql/schema_pgvector.sql`

**Contents**: CREATE EXTENSION vector; fru_sales_embeddings (with embedding VECTOR(1536)); batch_analytics; indexes.

#### 3.3.2 DB Setup Tool (Python)

**Path**: `tools/aws/setup_database.py`

**Purpose**: Python equivalent of legacy `module_infra_db/aws/setup-database.sh`

**Flow**:
1. Get `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `aurora_database_name` from `tofu output -json` on `infra_terraform/live_deploy/aws/scope_shared/durable`
2. **Ensure pgvector**: `aws rds-data execute-statement` with `CREATE EXTENSION IF NOT EXISTS vector;`
3. **Init schema**: Parse `core_app/sql/schema_pgvector.sql` (use `parse_sql_statements.py` or equivalent), execute each statement via RDS Data API
4. **Load data**: Invoke `load_openai_embeddings_to_pgvector_rds_api.py` with `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `PGDATABASE` in env

**Dependencies**: boto3, existing `core_app/backend/etl/load_openai_embeddings_to_pgvector_rds_api.py`

**Reference**: Legacy `module_infra_db/aws/setup-database.sh`, `init_schema_aws.sh`, `load_data_aws.sh`

---

### 3.4 Deploy Integration

**Path**: `tools/aws/deploy.py`

**Change**: Insert DB setup phase after Secrets (phase 5), before Build (phase 6).

**New phase** (e.g. Phase 5.5 or renumber):
- **Phase 5.5: Database setup** – Run `python tools/aws/setup_database.py --env <env>`
- Only run when Aurora exists (durable outputs include `db_cluster_arn`)
- Idempotent: setup_database skips if schema already initialized

**Phase order** (updated):
1. Doctor
2. Backend bootstrap
3. Shared durable (VPC + Aurora + Secrets)
4. Shared nondurable (ECR + S3)
5. Secrets values (ensure_secrets.py)
6. **Database setup** (setup_database.py) ← NEW
7. Build & push
8. ECR URLs
9. Apply stack (kube/nonkube)
10. Bootstrap (K8s/ECS)

**Update**: `tools/phases.py` – add "Database setup" to `deploy_phases()`.

---

### 3.5 ECS (Nonkube) Wiring

**Path**: `infra_terraform/live_deploy/aws/nonkube/main.tf`

**Changes**:
1. Pass Aurora outputs from `shared_durable` to ECS module:
   - `aurora_endpoint`, `aurora_port`, `aurora_database_name`, `aurora_security_group_id`
2. Add `aws_security_group_rule` in ECS module (or nonkube stack): allow Aurora SG ingress from ECS tasks SG
3. ECS module `env_vars`: Add `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` (from durable outputs)
4. `secret_arns`: Keep `PGPASSWORD` from durable (already present)

**Path**: `infra_terraform/modules/aws/ecs/variables.tf`

**New variables**:
- `aurora_endpoint`
- `aurora_port`
- `aurora_database_name`
- `aurora_security_group_id` (for SG rule)

**Path**: `infra_terraform/modules/aws/ecs/main.tf`

**Changes**:
- Add `aws_security_group_rule.aurora_from_ecs` when `aurora_security_group_id != ""`
- Add PGHOST, PGPORT, PGDATABASE, PGUSER to `env_list` (from vars)

**Spark task** (ECS): If Spark job needs DB, add same env vars. Legacy Spark may not; verify.

---

### 3.6 Kube Wiring

#### 3.6.1 Kube Stack: shared_nondurable + Aurora

**Path**: `infra_terraform/live_deploy/aws/kube/main.tf`

**Changes**:
1. Add `data "terraform_remote_state" "shared_nondurable"` (same pattern as nonkube)
2. Pass to EKS/k8s:
   - `ecr_app_url`, `ecr_spark_url`, `delta_bucket` from shared_nondurable
   - `aurora_endpoint`, `aurora_port`, `aurora_database_name`, `aurora_security_group_id` from shared_durable
3. EKS module (or k8s apply): Add security group rule for Aurora from EKS node/task SG

#### 3.6.2 K8s API Deployment: PG* Env Vars

**Path**: `infra_terraform/modules/cloud_shared/k8s/api-deployment.yaml`

**Current**: Placeholder values (PGHOST=fru-db, PGPASSWORD=postgres)

**Change**: Template or inject real values from Terraform outputs when applying.

**Options**:
- **A**: Use `tools/aws/kube_apply.py` to substitute `PGHOST`, `PGDATABASE`, `PGUSER` from durable outputs; keep `PGPASSWORD` as secretRef (create K8s secret from Secrets Manager or pass as env from external)
- **B**: Use Helm/ Kustomize with values from Terraform
- **C**: Create a K8s Secret for DB credentials, reference in deployment

**Recommended**: kube_apply.py reads durable outputs, substitutes `${PGHOST}`, `${PGDATABASE}`, `${PGUSER}` in api-deployment.yaml, and uses a K8s Secret for PGPASSWORD (populated from AWS Secrets Manager via CSI driver or init container).

**Simpler approach**: Pass all PG* as plain env vars from kube_apply (PGHOST, PGDATABASE, PGUSER) and PGPASSWORD as `valueFrom` secretKeyRef pointing to a K8s secret that is created from `aws secretsmanager get-secret-value` during bootstrap.

---

### 3.7 ETL Wiring

**Path**: `core_app/backend/etl/load_openai_embeddings_to_pgvector_rds_api.py`

**Expects**: `DB_CLUSTER_ARN`, `DB_SECRET_ARN` (and `PGDATABASE` if used)

**Usage**:
- **DB setup phase**: `setup_database.py` runs this script locally with env vars from durable outputs
- **ECS bootstrap**: If load_data runs as ECS task, task definition must include `DB_CLUSTER_ARN`, `DB_SECRET_ARN` as env vars (from Terraform outputs)
- **Kube**: Same for Job/CronJob – pass via env from ConfigMap/Secret populated from Terraform

**Action**: Ensure `setup_database.py` sets `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `PGDATABASE`, `CLOUD_REGION`/`AWS_REGION` before invoking the ETL script.

---

## 4. Task Checklist

| # | Task | Path / Scope |
|---|------|--------------|
| 1 | Create Aurora module | `infra_terraform/modules/aws/primitives/aurora/` |
| 2 | Add Aurora to durable stack | `infra_terraform/live_deploy/aws/scope_shared/durable/main.tf` |
| 3 | Add durable outputs | aurora_endpoint, aurora_port, aurora_database_name, aurora_security_group_id, db_cluster_arn, db_secret_arn |
| 4 | Copy schema file | `core_app/sql/schema_pgvector.sql` |
| 5 | Create setup_database.py | `tools/aws/setup_database.py` |
| 6 | Add parse_sql_statements.py (if missing) | `core_app/sql/` or `tools/` |
| 7 | Insert DB setup phase in deploy.py | After phase 5, before build |
| 8 | Update deploy_phases in phases.py | Add "Database setup" |
| 9 | ECS: Add Aurora outputs + env vars | nonkube/main.tf, infra_terraform/modules/aws/ecs |
| 10 | ECS: Add aurora_from_ecs SG rule | infra_terraform/modules/aws/ecs/main.tf |
| 11 | Kube: Add shared_nondurable remote state | infra_terraform/live_deploy/aws/kube/main.tf |
| 12 | Kube: Pass ecr_app_url, ecr_spark_url, delta_bucket to kube_apply | kube/main.tf, kube_apply.py |
| 13 | Kube: Pass PG* to api-deployment | kube_apply.py, api-deployment.yaml |
| 14 | Kube: Add aurora_from_eks SG rule | EKS module or kube stack |
| 15 | Ensure ensure_secrets sets db_password | tools/aws/ensure_secrets.py (verify) |

---

## 5. Dependencies and Order

```
1. Aurora module (standalone)
2. Durable: Add Aurora + outputs
3. Schema file + setup_database.py
4. Deploy: DB setup phase
5. ECS: Aurora env vars + SG rule
6. Kube: shared_nondurable + PG* + SG rule
```

---

## 6. References

- [AWS_AURORA_CLOUDFRONT_PLACEMENT.md](./AWS_AURORA_CLOUDFRONT_PLACEMENT.md) – Aurora and CloudFront placement
- [MIGRATION_ECS_COMBINED.md](./MIGRATION_ECS_COMBINED.md) – ECS module structure
- Legacy: `module_infra_basic/aws/terra/modules/aurora/`
- Legacy: `module_infra_db/aws/setup-database.sh`, `init_schema_aws.sh`, `load_data_aws.sh`
- Legacy: `module_infra_kubetypes/nonkube/aws/terra/modules/root_ecs/main.tf` (PGHOST, PGPORT, PGDATABASE in task def)
