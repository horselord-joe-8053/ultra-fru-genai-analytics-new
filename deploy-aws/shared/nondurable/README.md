# deploy-aws/shared/nondurable

Nondurable shared stack: S3 buckets (delta, artifacts) + ECR repos.

**Init:** The backend requires S3 config from `.env`. Use:

```bash
./init_with_backend.sh
```

(or from repo root: `./deploy-aws/shared/nondurable/init_with_backend.sh`)

Raw `terraform init -upgrade -reconfigure` will prompt for bucket and fail in non-interactive use.
