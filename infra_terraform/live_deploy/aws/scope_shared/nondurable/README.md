# infra_terraform/live_deploy/aws/scope_shared/nondurable

Nondurable shared stack: S3 buckets (delta, artifacts) + ECR repos.

**Init:** The backend requires S3 config from `.env`. From repo root, run:

```bash
./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh infra_terraform/live_deploy/aws/scope_shared/nondurable
```

(or with env: `./tools/aws/scope_shared/utils/init_terra_upgrade_reconfigure.sh infra_terraform/live_deploy/aws/scope_shared/nondurable dev`).  
Raw `tofu init -upgrade -reconfigure` will prompt for bucket and fail in non-interactive use. See the script header for full docs.
