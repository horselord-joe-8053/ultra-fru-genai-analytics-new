"""
Ensure secret values in cloud provider secret stores (AWS Secrets Manager, GCP Secret Manager).

Reads from .env: OPENAI_API_KEY, PGPASSWORD.
Used by both AWS and GCP deploy flows.

Usage:
  python tools/cloud_shared/ensure_secrets.py --provider aws --env dev
  python tools/cloud_shared/ensure_secrets.py --provider gcp --env dev
"""
import argparse
import json
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.cloud_shared.logging import logger
from tools.cloud_shared.retry import run_with_retry

load_dotenv()


def _get_aws_outputs(env: str, region: str) -> dict:
    """Get secret refs from AWS durable stack outputs."""
    from tools.aws.scope_shared.core.backend import backend_config, resolve_region
    from tools.aws.scope_shared.core.terra_runner import get_terra_env

    stack_dir = "infra_terraform/live_deploy/aws/scope_shared/durable"
    cfg = backend_config(stack_dir, env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    run_with_retry(
        [exe] + args,
        cwd=stack_dir,
        env=get_terra_env(region),
        description="tofu init for secrets",
    )
    out = subprocess.check_output(
        [exe, "output", "-json"],
        cwd=stack_dir,
        text=True,
        timeout=30,
        env=get_terra_env(region),
    )
    result = json.loads(out)
    return {
        "openai_api_key": result.get("openai_api_key_secret_arn", {}).get("value"),
        "db_password": result.get("db_password_secret_arn", {}).get("value"),
        "db_password_plain": result.get("db_password_plain_secret_arn", {}).get("value"),
    }


def _get_gcp_outputs(env: str, region: str) -> dict:
    """Get secret refs from GCP durable_with_cooloff stack (creates secrets). Use this stack
    so ensure_secrets can run before durable apply (durable has no state on first deploy)."""
    from tools.gcp.scope_shared.core.backend import backend_config, resolve_region
    from tools.gcp.scope_shared.core.terra_runner import get_terra_env

    stack_dir = "infra_terraform/live_deploy/gcp/scope_shared/durable_with_cooloff"
    cfg = backend_config(stack_dir, env, region, cloud="gcp")
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    run_with_retry(
        [exe] + args,
        cwd=stack_dir,
        env=get_terra_env(region),
        description="tofu init for secrets",
    )
    out = subprocess.check_output(
        [exe, "output", "-json"],
        cwd=stack_dir,
        text=True,
        timeout=30,
        env=get_terra_env(region),
    )
    result = json.loads(out)
    return {
        "openai_api_key": result.get("openai_api_key_secret_id", {}).get("value") or "",
        "db_password": result.get("db_password_secret_id", {}).get("value") or "",
        "db_password_plain": result.get("db_password_plain_secret_id", {}).get("value") or "",
        "google_ai_api_key": result.get("google_ai_api_key_secret_id", {}).get("value") or "",
        "claude_api_key": result.get("claude_api_key_secret_id", {}).get("value") or "",
    }


def _put_aws_secret(ref: str, value: str, region: str) -> None:
    """Set secret value in AWS Secrets Manager."""
    logger.info(f"[SECRETS] Setting secret ARN: {ref[:50]}...")
    subprocess.run(
        [
            "aws", "secretsmanager", "put-secret-value",
            "--secret-id", ref,
            "--secret-string", value,
            "--region", region,
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    logger.success("[SECRETS] Secret set successfully")


def _put_gcp_secret(secret_id: str, value: str, project_id: str) -> None:
    """Set secret value in GCP Secret Manager (add first version)."""
    logger.info(f"[SECRETS] Setting secret: {secret_id}...")
    subprocess.run(
        [
            "gcloud", "secrets", "versions", "add", secret_id,
            "--data-file=-",
            "--project", project_id,
        ],
        input=value,
        text=True,
        check=True,
        timeout=15,
        capture_output=True,
    )
    logger.success("[SECRETS] Secret set successfully")


def ensure_secrets(provider: str, env: str, region: str) -> None:
    """Ensure OPENAI_API_KEY and PGPASSWORD are set in the provider's secret store."""
    logger.step(f"Ensuring secrets in {'AWS Secrets Manager' if provider == 'aws' else 'GCP Secret Manager'}")

    if provider == "aws":
        outputs = _get_aws_outputs(env, region)
    elif provider == "gcp":
        outputs = _get_gcp_outputs(env, region)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    openai = (os.getenv("OPENAI_API_KEY") or "").strip()
    if openai:
        ref = outputs.get("openai_api_key")
        if not ref:
            raise KeyError("openai_api_key ref not in durable outputs; run deploy durable first")
        logger.info("[SECRETS] Setting OPENAI_API_KEY...")
        if provider == "aws":
            _put_aws_secret(ref, openai, region)
        else:
            project_id = os.getenv("GCP_PROJECT_ID", "").strip()
            if not project_id:
                raise ValueError("GCP_PROJECT_ID must be set for GCP ensure_secrets")
            _put_gcp_secret(ref, openai, project_id)
        logger.success("[SECRETS] OPENAI_API_KEY set")
    else:
        logger.warning("[SECRETS] OPENAI_API_KEY not set in .env; skipping")

    dbpw = (os.getenv("PGPASSWORD") or "").strip()
    if dbpw:
        if provider == "aws":
            ref = outputs.get("db_password")
            if not ref:
                raise KeyError("db_password_secret_arn not in durable outputs; run deploy durable first")
            logger.info("[SECRETS] Setting PGPASSWORD (RDS Data API JSON format)...")
            db_secret_json = json.dumps({"username": "postgres", "password": dbpw})
            _put_aws_secret(ref, db_secret_json, region)
            logger.success("[SECRETS] PGPASSWORD set (JSON)")

            ref_plain = outputs.get("db_password_plain")
            if ref_plain:
                logger.info("[SECRETS] Setting PGPASSWORD (plain for ECS)...")
                _put_aws_secret(ref_plain, dbpw, region)
                logger.success("[SECRETS] PGPASSWORD set (plain)")
            else:
                logger.warning("[SECRETS] db_password_plain not in outputs; ECS may fail")
        else:
            ref_plain = outputs.get("db_password_plain")
            if not ref_plain:
                raise KeyError("db_password_plain_secret_id not in durable outputs; run deploy durable first")
            project_id = os.getenv("GCP_PROJECT_ID", "").strip()
            if not project_id:
                raise ValueError("GCP_PROJECT_ID must be set for GCP ensure_secrets")
            logger.info("[SECRETS] Setting PGPASSWORD (plain)...")
            _put_gcp_secret(ref_plain, dbpw, project_id)
            logger.success("[SECRETS] PGPASSWORD set")
    else:
        logger.warning("[SECRETS] PGPASSWORD not set in .env; skipping")

    if provider == "gcp":
        google_ai = (os.getenv("GOOGLE_AI_API_KEY") or "").strip()
        if google_ai:
            ref = outputs.get("google_ai_api_key")
            if ref:
                logger.info("[SECRETS] Setting GOOGLE_AI_API_KEY...")
                project_id = os.getenv("GCP_PROJECT_ID", "").strip()
                if not project_id:
                    raise ValueError("GCP_PROJECT_ID must be set for GCP ensure_secrets")
                _put_gcp_secret(ref, google_ai, project_id)
                logger.success("[SECRETS] GOOGLE_AI_API_KEY set")
            else:
                logger.warning("[SECRETS] google_ai_api_key_secret_id not in durable outputs; agent may be disabled")
        else:
            logger.warning("[SECRETS] GOOGLE_AI_API_KEY not set in .env; agent-based query will be disabled")

        claude_api = (os.getenv("CLAUDE_API_KEY") or "").strip()
        if claude_api:
            ref = outputs.get("claude_api_key")
            if ref:
                logger.info("[SECRETS] Setting CLAUDE_API_KEY...")
                project_id = os.getenv("GCP_PROJECT_ID", "").strip()
                if not project_id:
                    raise ValueError("GCP_PROJECT_ID must be set for GCP ensure_secrets")
                _put_gcp_secret(ref, claude_api, project_id)
                logger.success("[SECRETS] CLAUDE_API_KEY set")
            else:
                logger.warning("[SECRETS] claude_api_key_secret_id not in durable outputs; run deploy durable_with_cooloff first")
        else:
            logger.warning("[SECRETS] CLAUDE_API_KEY not set in .env; skip (use GCP_LLM_PROVIDER=claude to avoid Gemini quota)")

    logger.success("[SECRETS] All secrets ensured")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ensure secrets in cloud provider secret store")
    ap.add_argument("--provider", choices=["aws", "gcp"], default=os.getenv("CLOUD_PROVIDER", "aws"))
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    if args.provider == "aws":
        from tools.aws.scope_shared.core.backend import resolve_region
    else:
        from tools.gcp.scope_shared.core.backend import resolve_region

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region

    try:
        ensure_secrets(args.provider, args.env, region)
        sys.exit(0)
    except Exception as e:
        logger.error(f"[SECRETS] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
