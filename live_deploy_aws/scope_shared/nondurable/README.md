# live_deploy_aws/scope_shared/nondurable

Nondurable shared stack: S3 buckets (delta, artifacts) + ECR repos.

**Init:** The backend requires S3 config from `.env`. From repo root, run:

```bash
./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh live_deploy_aws/scope_shared/nondurable
```

(or with env: `./tools/aws/common/utils/init_terra_upgrade_reconfigure.sh live_deploy_aws/scope_shared/nondurable dev`).  
Raw `tofu init -upgrade -reconfigure` will prompt for bucket and fail in non-interactive use. See the script header for full docs.
