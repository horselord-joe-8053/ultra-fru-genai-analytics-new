
"""
Ensure Secrets Manager secret values are present (without storing them in Terraform state).

Usage:
  python tools/aws/ensure_secrets.py --env dev

Reads from `.env`:
- OPENAI_API_KEY
- DB_PASSWORD or PGPASSWORD
"""
import argparse, os, subprocess, json
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config

load_dotenv()

def init_stack(env):
    cfg = backend_config("deploy-aws/shared/durable", env)
    args = ["init","-upgrade"]
    for c in cfg:
        args += ["-backend-config", c]
    tofu(args, cwd="deploy-aws/shared/durable")

def outputs(env):
    init_stack(env)
    out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd="deploy-aws/shared/durable", text=True)
    return json.loads(out)

def put_value(secret_arn, value, region):
    cmd = ["aws","secretsmanager","put-secret-value","--secret-id",secret_arn,"--secret-string",value,"--region",region]
    subprocess.run(cmd, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()

    region = require("AWS_REGION")
    o = outputs(args.env)

    openai = os.getenv("OPENAI_API_KEY","").strip()
    if openai:
        put_value(o["openai_api_key_secret_arn"]["value"], openai, region)
        print("Set OPENAI_API_KEY secret value.")
    else:
        print("WARN: OPENAI_API_KEY not set in .env; skipping.")

    dbpw = (os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD") or "").strip()
    if dbpw:
        put_value(o["db_password_secret_arn"]["value"], dbpw, region)
        print("Set DB_PASSWORD secret value.")
    else:
        print("WARN: DB_PASSWORD/PGPASSWORD not set in .env; skipping.")

if __name__ == "__main__":
    main()
