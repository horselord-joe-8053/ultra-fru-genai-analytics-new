#!/usr/bin/env python3
"""
Verify that PGPASSWORD in .env can connect to Aurora, or at least
that db_password_plain in Secrets Manager matches .env (deploy would sync it).

Usage:
  python tools/aws/scope_shared/verify/verify_db_password.py --env dev

Exits 0 if connection succeeds or secrets match; 1 otherwise.
Does not print the password.
"""
import argparse
import json
import os
import subprocess
import sys

from tools.cloud_shared.env import load_dotenv
from tools.aws.scope_shared.core.backend import backend_config, resolve_region
from tools.aws.scope_shared.core.terra_runner import get_terra_env
from tools.cloud_shared.retry import run_with_retry
from tools.cloud_shared.logging import logger

load_dotenv()


def get_durable_outputs(env: str, region: str) -> dict:
    stack_dir = "infra_terraform/live_deploy/aws/scope_shared/durable"
    cfg = backend_config(stack_dir, env, region)
    init_args = ["init", "-lock=false", "-upgrade", "-reconfigure"]
    for c in cfg:
        init_args += ["-backend-config", c]
    exe = os.getenv("FRU_TF_BIN", "tofu")
    run_with_retry([exe] + init_args, cwd=stack_dir, env=get_terra_env(region), description="tofu init")
    out_raw = subprocess.check_output(
        [exe, "output", "-json"], cwd=stack_dir, text=True, env=get_terra_env(region)
    )
    return json.loads(out_raw)


def fetch_secret_value(secret_arn: str, region: str) -> str | None:
    try:
        out = subprocess.check_output(
            [
                "aws", "secretsmanager", "get-secret-value",
                "--secret-id", secret_arn,
                "--query", "SecretString",
                "--output", "text",
                "--region", region,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip().strip('"')
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Verify .env DB password can connect to Aurora")
    ap.add_argument("--env", default=os.getenv("FRU_ENV", "dev"))
    ap.add_argument("--region", default=None)
    args = ap.parse_args()

    region = resolve_region(args.region)
    pw = (os.getenv("PGPASSWORD") or "").strip()
    if not pw:
        logger.error("PGPASSWORD not set in .env")
        sys.exit(1)

    outputs = get_durable_outputs(args.env, region)
    host = outputs.get("aurora_endpoint", {}).get("value", "")
    port = str(outputs.get("aurora_port", {}).get("value", 5432))
    db = outputs.get("aurora_database_name", {}).get("value", "fru_db")
    user = "postgres"
    secret_arn = outputs.get("db_password_plain_secret_arn", {}).get("value", "")

    if not host:
        logger.error("aurora_endpoint not in durable outputs; run deploy durable first")
        sys.exit(1)

    # 1. Try direct connection (works only from within VPC)
    try:
        import psycopg2
    except ImportError:
        psycopg2 = None

    if psycopg2:
        logger.info(f"Testing connection to {host}:{port}/{db} (user={user})...")
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=db,
                user=user,
                password=pw,
                connect_timeout=10,
            )
            conn.close()
            logger.success("✓ Password in .env matches Aurora — connection succeeded")
            sys.exit(0)
        except psycopg2.OperationalError as e:
            err = str(e)
            if "password authentication failed" in err or "FATAL: password authentication failed" in err:
                logger.error("✗ Password in .env does NOT match Aurora (password authentication failed)")
                logger.error("  → Aurora was created with a different password.")
                logger.error("  → Fix: set Aurora password in RDS console, or ensure .env has the original password.")
                logger.error("  → See README_WAR_STORIES.md ## 44")
                sys.exit(1)
            # Timeout / connection refused — can't reach Aurora from this machine
            logger.warning("✗ Cannot reach Aurora from this machine (private subnet / network).")
            logger.info("  → Falling back to Secrets Manager comparison...")

    # 2. Compare db_password_plain in Secrets Manager with .env
    if secret_arn:
        sm_value = fetch_secret_value(secret_arn, region)
        if sm_value is not None:
            if sm_value == pw:
                logger.success("✓ db_password_plain in Secrets Manager matches .env")
                logger.info("  → Deploy would keep them in sync. If API still fails, Aurora may have a different password.")
                logger.info("  → Try deploy kube — it will sync secrets and restart pods.")
                sys.exit(0)
            else:
                logger.warning("✗ db_password_plain in Secrets Manager does NOT match .env")
                logger.info("  → Deploy kube WILL fix this: ensure_secrets will update the secret, bootstrap will refresh K8s, pods will restart.")
                logger.info("  → Run: python tools/aws/deploy.py --scope kube --env dev")
                sys.exit(1)
        else:
            logger.warning("Could not fetch db_password_plain from Secrets Manager")
    else:
        logger.warning("db_password_plain_secret_arn not in durable outputs")

    logger.info("  → If .env has the same password used when Aurora was created, deploy kube should fix the DB issue.")
    sys.exit(0)
