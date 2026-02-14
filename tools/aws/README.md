
# AWS Tools

## One-line deploy / teardown
```bash
python tools/aws/deploy.py --scope kube --env dev
python tools/aws/deploy.py --scope nonkube --env dev

python tools/aws/teardown.py --scope kube --env dev --force
python tools/aws/teardown.py --scope nonkube --env dev --force
python tools/aws/teardown.py --scope all --env dev --force
```

## Backend bootstrap
```bash
python tools/aws/bootstrap_state_backend.py
```

## Durable destroy (explicit)
```bash
ALLOW_DURABLE_DESTROY=YES python tools/aws/destroy_durable.py --env dev --force
```

## Manual init for a single stack

If you want to run `tofu plan` (or init) by hand in a stack directory without the deploy pipeline, use:

```bash
./tools/aws/utils/init_terra_upgrade_reconfigure.sh live-deploy-aws/shared/nondurable
```

See [tools/aws/utils/README.md](utils/README.md) for details.

## Notes
- ECS Spark **recurring schedule** is Terraform-managed.
- ECS Spark **bootstrap run** is invoked once by `tools/aws/deploy.py`.
