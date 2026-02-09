
# State Recovery (Post-Nuclear Cleanup)

## Steps
1. Recreate backend:
```bash
python tools/aws/bootstrap_state_backend.py
```

2. Re-run deploy (recreates missing resources):
```bash
python tools/aws/deploy.py --scope kube --env dev
```

3. If resources exist but state is missing:
- Use `tools/aws/reconcile_state.py` to list tagged resources.
- Import critical resources into the correct stack state using:
```bash
python tools/aws/import_state.py <stack_dir> <addr> <id>
```
Examples:
- `deploy-aws/shared/durable`
- `deploy-aws/shared/nondurable`
- `deploy-aws/kube`
- `deploy-aws/nonkube`
