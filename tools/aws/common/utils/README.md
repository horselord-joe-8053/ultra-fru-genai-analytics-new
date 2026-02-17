# AWS deploy utilities

## init_terra_upgrade_reconfigure.sh

**Purpose:** Run OpenTofu (or Terraform) `init -upgrade -reconfigure` with S3 backend config from `.env` so the backend does not prompt for bucket/key/region. Use when you want to init a single stack by hand (e.g. to run `tofu plan` locally) without using the full deploy pipeline.

**How to run:** From the **repo root** only:

```bash
./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh <stack_dir> [env]
```

Examples:

```bash
./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh live_deploy_aws/scope_shared/nondurable
./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh live_deploy_aws/scope_shared/durable dev
./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh live_deploy_aws/nonkube dev
```

**Requirements:** `.env` (or `.env.fru`) with at least `TF_STATE_BUCKET`, `CLOUD_REGION`. Optional: `TF_STATE_PREFIX`/`FRU_PREFIX`, `FRU_ENV`, `TF_LOCK_TABLE`/`TF_STATE_LOCK_TABLE`.

After running, you can `tofu plan` / `apply` / `destroy` from that stack directory. Use `TF_DATA_DIR=$REPO_ROOT/tofu_data` if you follow the project convention (the script sets it for the init run).
