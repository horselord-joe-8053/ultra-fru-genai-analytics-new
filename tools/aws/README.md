
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

## Notes
- ECS Spark **recurring schedule** is Terraform-managed.
- ECS Spark **bootstrap run** is invoked once by `tools/aws/deploy.py`.
