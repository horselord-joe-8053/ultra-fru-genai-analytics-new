
# FRU Umbrella Project (Runnable + AWS Complete)

## Table of Contents
1. Prereqs
2. Configure
3. One-line Deploy
4. One-line Teardown
5. Durable Destroy (Explicit)
6. Directory Layout
7. State Recovery

## 1. Prereqs
- OpenTofu (`tofu`) or Terraform
- AWS CLI authenticated
- Docker
- kubectl (kube path)

## 2. Configure
This repo ships with a `.env` (copied from your provided example). Edit it:
```bash
# edit .env
```

## 3. One-line Deploy (AWS)

### Kube (EKS)
```bash
python tools/aws/deploy.py --scope kube --env dev
```

### Nonkube (ECS)
```bash
python tools/aws/deploy.py --scope nonkube --env dev
```

## 4. One-line Teardown (AWS)
```bash
python tools/aws/teardown.py --scope kube --env dev --force
python tools/aws/teardown.py --scope nonkube --env dev --force
python tools/aws/teardown.py --scope all --env dev --force
```

## 5. Durable Destroy (Explicit, Dangerous)
```bash
ALLOW_DURABLE_DESTROY=YES python tools/aws/standalone/destroy_durable.py --env dev --force
```

## 6. Directory Layout
- `infra_terraform/live_deploy/aws/`
  - `shared/durable/`
  - `shared/nondurable/`
  - `kube/`
  - `nonkube/`
- `infra_terraform/live_deploy/gcp/` (phase-1 minimal parity)

## 7. State Recovery
See `STATE_RECOVERY.md`.
