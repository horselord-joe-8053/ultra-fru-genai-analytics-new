# AWS Authentication: A Systematic Guide for This Project

This document organizes all AWS authentication and access components we encounter—secrets, IAM roles, keys, profiles—and how each part of our system uses them. **It assumes very little prior AWS knowledge**; we explain each concept as we go.

---

## 1. The Big Picture: Two Worlds of Auth

<table>
<tr style="background:#e3f2fd"><th>World</th><th>Who/What</th><th>Credential Type</th><th>Used For</th></tr>
<tr><td><b>Human / CI</b></td><td>You, deploy scripts, Terraform, AWS CLI</td><td>Access keys <i>or</i> SSO profile</td><td>Deploy, teardown, ensure_secrets, doctor</td></tr>
<tr style="background:#f1f8e9"><td><b>Workload</b></td><td>ECS tasks, EKS pods, Spark jobs</td><td>IAM roles <i>or</i> static keys</td><td>Bedrock, S3, RDS Data API, Secrets Manager</td></tr>
</table>

**Why not just one choice in each row?**

- **Human / CI:** We'd like to use only SSO (safer, no long-lived keys), but CI pipelines and EKS bootstrap can't run `aws sso login` interactively—they need access keys. So we support both: profile for local dev, keys for CI and headless scripts.
- **Workload:** We'd like to use only IAM roles (no keys to manage). But EKS pods don't get automatic IAM credentials like ECS. We must inject credentials ourselves, and the only thing we can inject is **static keys** (the same access keys from `.env`). So: ECS uses roles; EKS uses static keys.

---

## 1.5 Core Concepts: IAM, Policies, Roles, SSO

### IAM (Identity and Access Management)

**IAM** is AWS's system for controlling *who* can do *what* with your resources. Every API call is checked against IAM rules before it's allowed.

### IAM Policy

An **IAM policy** is a JSON document that defines permissions. It answers: *"Allow or deny which actions on which resources?"*

| Field | Meaning | Example |
|:------|:--------|:--------|
| **Effect** | Allow or Deny | `Allow` |
| **Action** | Which API operations | `s3:GetObject`, `secretsmanager:GetSecretValue` |
| **Resource** | Which resources (often ARNs) | `arn:aws:s3:::my-bucket/*` or `*` for all |

**In our project:** The ECS **execution role** has an inline policy that allows `secretsmanager:GetSecretValue` on our three secret ARNs. Without it, the ECS agent would get AccessDenied when trying to fetch secrets before starting the container.

### IAM Role

An **IAM role** is an identity that can be *assumed* by someone or something. Unlike an IAM user, a role doesn't have long‑lived passwords or keys. Instead, you *assume* the role and get **temporary credentials**.

| Identity | Has permanent credentials? | Typical use |
|:---------|:---------------------------|:------------|
| **IAM User** | Yes (access keys, password) | Humans, CI, scripts |
| **IAM Role** | No; assumed to get temp creds | ECS tasks, Lambda, EC2, SSO |

**In our project:** ECS tasks assume a **task role**. AWS injects temporary credentials into the container. The role has IAM policies for Bedrock and S3. The container never sees access keys.

### SSO (Single Sign-On)

**SSO** in AWS usually means **IAM Identity Center** (formerly AWS SSO). You sign in once via `aws sso login`, and AWS gives you **temporary credentials** instead of long‑lived access keys. Your `~/.aws/credentials` profile is updated with those temp creds. When you use `AWS_PROFILE=admin`, the CLI uses those temp creds.

---

## 2. Credential Types at a Glance

- **Human / CI:** Profile (preferred for local dev) or Access Keys (for CI, EKS aws-credentials).
- **ECS:** Execution role (ECR, Secrets Manager) + Task role (Bedrock, S3).
- **EKS:** K8s secrets: `db-credentials`, `app-credentials` (from Secrets Manager), `aws-credentials` (static keys from `.env`).

---

## 3. Human / CI Credentials

| Source | What it is | Use Case |
|:-------|:-----------|:---------|
| **Profile** | Named entry in `~/.aws/credentials`; select with `AWS_PROFILE=admin` | Preferred when `FRU_AWS_USE_PROFILE=true` |
| **Access Keys** | `AWS_ADMIN_ACCESS_KEY_ID`, `AWS_ADMIN_SECRET_ACCESS_KEY` from `.env` | Default; CI and headless scripts |
| **SSO** | `aws sso login` + profile | When your org uses IAM Identity Center |

---

## 4. Workload Credentials (ECS vs EKS)

### ECS: IAM Roles (No Static Keys)

ECS tasks assume IAM roles. AWS injects temporary credentials into the container automatically. Execution role: ECR pull, Secrets Manager. Task role: Bedrock, S3.

### EKS: K8s Secrets (Static Keys)

EKS pods do **not** get instance metadata like ECS. We inject AWS credentials via **Kubernetes secrets** (from `.env`). K8s secrets: `db-credentials`, `app-credentials` (Secrets Manager), `aws-credentials` (static keys).

---

## 5. Secrets Manager

| Secret Name | Format | Value |
|:------------|:-------|:------|
| `fru/dev/openai_api_key-{region}` | Plain string | OpenAI API key |
| `fru/dev/db_password-{region}` | JSON `{"username":"postgres","password":"..."}` | RDS Data API |
| `fru/dev/db_password_plain-{region}` | Plain string | ECS/EKS env (PGPASSWORD) |

---

## 6. Component Access Matrix

| Component | S3 | ECR | Secrets Manager | Bedrock | Aurora |
|-----------|:--:|:---:|:---------------:|:-------:|:------:|
| Deploy (human) | ✅ | ✅ | put | — | — |
| ECS API task | task role | — | exec role | task role | PGPASSWORD |
| ECS Spark task | task role | — | exec role | — | PGPASSWORD |
| EKS API pod | aws-credentials | — | — | aws-credentials | db-credentials |
| EKS Spark pod | aws-credentials | — | — | — | db-credentials |

---

## 7. Common Auth Issues and Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Unable to locate credentials` | No keys, no profile, or SSO expired | Set `AWS_PROFILE=admin`; run `aws sso login` |
| `AuthFailure` / `SignatureDoesNotMatch` | Stale keys in .env | Set `FRU_AWS_USE_PROFILE=true` to prefer profile |
| EKS: "Unable to locate credentials" | aws-credentials secret missing or empty | Run bootstrap with `AWS_ADMIN_*` in .env |
| EKS Spark: S3 AccessDenied | aws-credentials has Bedrock-only user | Use **admin** credentials (Bedrock + S3) |
| ECS: ImagePullBackOff | Execution role can't pull ECR | Execution role has AmazonECSTaskExecutionRolePolicy |
| ECS: Secret not found | Execution role lacks GetSecretValue | Attach policy with `secretsmanager:GetSecretValue` on secret ARNs |

---

## 8. Quick Reference: Env Vars

| Variable | Purpose |
|:---------|:--------|
| `AWS_PROFILE` | Use named profile from `~/.aws/credentials` |
| `AWS_ADMIN_ACCESS_KEY_ID` | Long-lived IAM user key (deploy, K8s aws-credentials) |
| `AWS_ADMIN_SECRET_ACCESS_KEY` | Matching secret |
| `FRU_AWS_USE_PROFILE` | When `true`, deploy uses profile over `AWS_ADMIN_*` |
| `OPENAI_API_KEY` | Written to Secrets Manager by ensure_secrets |
| `PGPASSWORD` | Written to Secrets Manager by ensure_secrets |

---

## 9. Diagnostic Commands

```bash
# What credentials am I using?
python tools/aws/diagnose_auth.py

# Verify AWS identity
AWS_PROFILE=admin aws sts get-caller-identity

# Test Terraform env (what tofu sees)
python -c "from tools.aws.scope_shared.core.terra_runner import get_terra_env; e=get_terra_env('us-east-1'); print('AWS_ACCESS_KEY_ID' in e, 'AWS_PROFILE' in e)"
```
