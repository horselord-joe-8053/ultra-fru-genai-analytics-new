
"""
Ensure Secrets Manager secret values are present (without storing them in Terraform state).

Usage:
  python tools/aws/ensure_secrets.py --env dev

Reads from `.env`:
- OPENAI_API_KEY
- PGPASSWORD
"""
import argparse, os, subprocess, json, sys
from tools._env import load_dotenv, require
from tools.tofu_runner import get_tofu_env
from tools.aws._backend import backend_config, resolve_region
from tools.subprocess_retry import run_with_retry
from tools import logger

load_dotenv()

def init_stack(env, region=None):
    logger.info("[SECRETS] Initializing shared/durable stack...")
    cfg = backend_config("live-deploy-aws/shared/durable", env, region)
    args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    cmd = [exe] + args
    run_with_retry(cmd, cwd="live-deploy-aws/shared/durable", env=get_tofu_env(region), description="tofu init for secrets")
    logger.success("[SECRETS] Stack initialized")

def outputs(env, region=None):
    logger.info("[SECRETS] Getting terraform outputs...")
    init_stack(env, region)
    out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd="live-deploy-aws/shared/durable", text=True, timeout=30, env=get_tofu_env(region))
    result = json.loads(out)
    logger.success("[SECRETS] Outputs retrieved")
    return result

def put_value(secret_arn, value, region):
    logger.info(f"[SECRETS] Setting secret ARN: {secret_arn[:50]}...")
    cmd = ["aws","secretsmanager","put-secret-value","--secret-id",secret_arn,"--secret-string",value,"--region",region]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        logger.success(f"[SECRETS] Secret set successfully")
    except subprocess.TimeoutExpired:
        logger.error("[SECRETS] put-secret-value timed out")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"[SECRETS] Failed to set secret: {e.stderr.decode() if e.stderr else str(e)}")
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region

    logger.step("Ensuring secrets in AWS Secrets Manager")

    try:
        logger.info(f"[SECRETS] Region: {region}")
        
        logger.info("[SECRETS] Getting terraform outputs...")
        o = outputs(args.env, region)

        openai = os.getenv("OPENAI_API_KEY","").strip()
        if openai:
            arn = o.get("openai_api_key_secret_arn", {}).get("value")
            if not arn:
                raise KeyError("openai_api_key_secret_arn not in durable outputs; run deploy durable first")
            logger.info("[SECRETS] Setting OPENAI_API_KEY...")
            put_value(arn, openai, region)
            logger.success("[SECRETS] OPENAI_API_KEY set")
        else:
            logger.warning("[SECRETS] OPENAI_API_KEY not set in .env; skipping")

        dbpw = (os.getenv("PGPASSWORD") or "").strip()
        if dbpw:
            # RDS Data API (setup_database) needs JSON format
            arn = o.get("db_password_secret_arn", {}).get("value")
            if not arn:
                raise KeyError("db_password_secret_arn not in durable outputs; run deploy durable first")
            logger.info("[SECRETS] Setting PGPASSWORD (RDS Data API JSON format)...")
            db_secret_json = json.dumps({"username": "postgres", "password": dbpw})
            put_value(arn, db_secret_json, region)
            logger.success("[SECRETS] PGPASSWORD set (JSON)")

            # ECS needs plain string (legacy: db_password_plain; ECS doesn't support JSON key extraction)
            arn_plain = o.get("db_password_plain_secret_arn", {}).get("value")
            if arn_plain:
                logger.info("[SECRETS] Setting PGPASSWORD (plain for ECS)...")
                put_value(arn_plain, dbpw, region)
                logger.success("[SECRETS] PGPASSWORD set (plain)")
            else:
                logger.warning("[SECRETS] db_password_plain_secret_arn not in outputs; ECS may fail")
        else:
            logger.warning("[SECRETS] PGPASSWORD not set in .env; skipping")

        logger.success("[SECRETS] All secrets ensured")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[SECRETS] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
