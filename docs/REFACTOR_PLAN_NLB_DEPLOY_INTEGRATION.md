# Refactor Plan: NLB Controller Integration into Deploy Flow

**Status: Implemented.** (2026-02)

Integrate the AWS Load Balancer Controller (and eksctl) installation into the main kube deploy flow for the NLB track. Make the install logic Python-based for cross-platform support (Windows, macOS, Linux).

---

## Goals

1. **NLB track:** When deploying kube without `--elb`, the controller is installed automatically before kube_apply.
2. **ELB track:** When `--elb` is used, skip controller install (in-tree Classic ELB).
3. **Cross-platform:** Install logic in Python (not shell) so it runs on Windows without WSL/Git Bash.

---

## Current State

| Component | Location | When run |
|-----------|----------|----------|
| Install script | `tools/aws/kube/install_aws_load_balancer_controller.sh` | Manual, before deploy |
| Deploy flow | `deploy_kube.py` | EKS tofu apply → kube_apply → LB poll → frontend |

---

## Refactor Steps

### 1. Convert install script to Python (required)

**Create:** `tools/aws/kube/install_aws_load_balancer_controller.py`

- Port all logic from `.sh` to Python using `subprocess.run()`.
- Use `load_dotenv`, `require`, `resolve_region` for env.
- Steps to implement:
  1. `eksctl utils associate-iam-oidc-provider` (or continue on failure)
  2. Create IAM policy if not exists (fetch JSON via `urllib` or `requests`, `aws iam create-policy`)
  3. `eksctl create iamserviceaccount`
  4. `helm repo add` / `helm repo update`
  5. Get VPC ID via `aws eks describe-cluster`
  6. `helm upgrade --install aws-load-balancer-controller`
  7. `kubectl wait` for deployment
- Idempotent: exit 0 if controller already installed and healthy.
- Accept `--env`, `--region`, `--profile` (or `AWS_PROFILE`).

**Deprecate:** `install_aws_load_balancer_controller.sh` — use `install_aws_load_balancer_controller.py` instead.

**Rationale for Python:** Shell scripts do not run natively on Windows. Python ensures the deploy flow works on Windows without WSL or Git Bash.

### 2. Integrate into deploy_kube.py

**When:** NLB track only (`not getattr(args, "elb", False)`).

**Where:** After Phase 9 (EKS tofu apply), before Phase 10 (kube_apply bootstrap).

```python
# Phase 9.5: Install AWS Load Balancer Controller (NLB track only)
if not getattr(args, "elb", False):
    def _install_nlb():
        subprocess.run([
            sys.executable, "tools/aws/kube/install_aws_load_balancer_controller.py",
            "--env", env, "--region", region,
        ], check=True, env={**os.environ, "CLOUD_REGION": region})
    _timed("Install NLB controller", "install_aws_load_balancer_controller", _install_nlb)
```

### 3. Doctor checks for NLB track

When `scope` in (`kube`, `all`) and not `--elb`:

- Require `eksctl` in PATH.
- Require `helm` in PATH.

Add to `tools/aws/standalone/doctor.py` (or scope-aware check). Fail deploy early if missing.

### 4. Update docs

- `docs/KUBE_NLB_MIGRATION_STEPS.md`: Remove manual Step 1; state install runs automatically in deploy.
- `docs/KUBE_LOAD_BALANCER_CLARIFICATION.md`: Update prerequisite to "install runs automatically when deploying kube (NLB track)".

---

## Summary

| Item | Action |
|------|--------|
| **Python conversion** | **Required.** Create `install_aws_load_balancer_controller.py`; deprecate `.sh`. |
| **Integration** | Add install step in `deploy_kube.py` after EKS apply, before kube_apply, when not `--elb`. |
| **Doctor** | Add `eksctl` and `helm` checks for NLB track. |
| **Idempotency** | Install script exits 0 if controller already installed and healthy. |
| **Docs** | Update migration and clarification docs. |
