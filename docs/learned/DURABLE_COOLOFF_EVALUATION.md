# Durable Resources with 30-Day Cool-Off: Evaluation

## A.1 Why `recovery_window_in_days = 30` in secrets.tf?

**Yes.** The `recovery_window_in_days` parameter controls the AWS Secrets Manager recovery window. When Terraform destroys a secret, AWS schedules it for deletion. During that period (default 30 days):

- The secret is in "scheduled for deletion" state
- **You cannot create a new secret with the same name** until the old one is either restored or permanently deleted
- You can call `RestoreSecret` to cancel deletion and reuse the secret

So the "curse" is the side effect: same-name recreation is blocked for up to 30 days. We set it explicitly for recovery capability (restore if teardown was accidental); the cool-off is the unavoidable consequence.

**Alternative:** `ForceDeleteWithoutRecovery` would allow immediate same-name recreation but is irreversible—no restore. We do not use it.

---

## A.2 Components with 30-Day Cool-Off in Our Stacks

| AWS Resource | Has Cool-Off? | In Our Stacks? | Location |
|--------------|---------------|----------------|----------|
| **Secrets Manager** | Yes (7–30 days, configurable) | Yes | `durable/secrets.tf` (3 secrets) |
| **KMS keys** | Yes (7–30 days, cannot bypass) | No (Aurora uses default AWS KMS) | — |
| **S3 buckets** | No (immediate; name released after delete) | — | — |
| **ECR repos** | No | — | — |
| **VPC, Aurora, etc.** | No | — | — |

**Conclusion:** Only **Secrets Manager secrets** in our durable stack have this behavior. No other resources in our Terraform have a mandatory cool-off.

---

## A.2 Evaluation: `durable_with_cooloff/` Split

### Proposal

- **`durable/`** — VPC, Aurora, DB subnet group (no cool-off)
- **`durable_with_cooloff/`** — Secrets Manager secrets only (30-day cool-off)
- **`--incl-dura`** — Destroys `durable` only (VPC, Aurora). Secrets remain.
- **`--incl-dura-all`** — Destroys both `durable` and `durable_with_cooloff` (full teardown, current `--incl-dura` behavior)

### Pros

| Benefit | Notes |
|---------|-------|
| **Faster re-deploy after teardown** | VPC + Aurora can be recreated immediately; no 30-day wait for secrets |
| **Safer teardown** | Normal teardown keeps secrets; accidental teardown doesn’t block same-name recreate |
| **Clear separation** | Cool-off resources isolated; easier to reason about |

### Cons

| Drawback | Notes |
|----------|-------|
| **Deploy complexity** | Durable outputs (secret ARNs) come from two stacks; deploy must read both |
| **Dependency order** | `durable` may need secret ARNs (e.g. for Aurora); currently secrets are in same stack |
| **Two state files** | More Terraform state to manage |
| **Secret ARN wiring** | Nondurable/kube/nonkube consume `db_password_secret_arn`, etc.; need `terraform_remote_state` or outputs from `durable_with_cooloff` |

### Dependency Check

- **Aurora:** Uses `aurora_master_password` from Terraform var (from `.env`), not Secrets Manager ARN. Secrets are populated by `ensure_secrets.py` after Terraform.
- **Nondurable/Kube/Nonkube:** Read secret ARNs from durable outputs. If secrets move to `durable_with_cooloff`, those stacks need outputs from that stack.

### Recommendation

**Worth doing if** you frequently teardown and redeploy the same region and hit the 30-day block. The refactor is moderate: split secrets into a new stack, add `terraform_remote_state` for secret ARNs, and update teardown flags.

**Defer if** teardown-with-durable is rare. The restore workaround (`aws secretsmanager restore-secret`) is acceptable for occasional use.

### As Implemented

1. **`infra_terraform/live_deploy/aws/scope_shared/durable_with_cooloff/`** exists with secrets only.
2. Secrets are standalone; durable has no secrets. Nondurable/kube read them via `tofu output` from durable. So we need: durable_with_cooloff outputs secret ARNs; durable outputs everything else. Deploy and other tools today read from durable. We’d need to either:
   Deploy and tools read from both stacks as needed (durable_with_cooloff applied first).
3. **`teardown.py`:** `--incl-dura` destroys durable only (VPC, Aurora); secrets remain. `--incl-dura-all` destroys durable then durable_with_cooloff.
4. **Deploy:** Applies durable_with_cooloff before durable; tools read from the appropriate stack outputs.

---

## Migration (Existing Deployments)

If you have an **existing** deployment where secrets are in the `durable` state:

1. **Import** existing secrets into durable_with_cooloff (deploy does this automatically).
2. **Remove secrets from durable state** (keeps secrets in AWS):
   ```bash
   cd infra_terraform/live_deploy/aws/scope_shared/durable
   tofu state rm aws_secretsmanager_secret.openai_api_key
   tofu state rm aws_secretsmanager_secret.db_password
   tofu state rm aws_secretsmanager_secret.db_password_plain
   ```
3. **Apply durable** — it will read secret ARNs from durable_with_cooloff via remote state.

For **fresh** deployments, no migration needed.
