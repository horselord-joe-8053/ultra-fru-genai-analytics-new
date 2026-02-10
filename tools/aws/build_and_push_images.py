
"""
Build and push ECR images for app and spark.

One-liners:
  python tools/aws/build_and_push_images.py --env dev

This tool:
- Reads ECR repository URLs from `deploy-aws/shared/nondurable` state
- Logs into ECR properly
- Builds and pushes images

Replace the build contexts to match your legacy project.
"""
import argparse, os, json, subprocess
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config

load_dotenv()

def sh(cmd, input_text=None):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, input=input_text, text=True, check=True)

def tofu_output_json(stack_dir: str, env: str):
    cfg = backend_config(os.path.basename(stack_dir), env)
    args = ["init","-upgrade"]
    for c in cfg:
        args += ["-backend-config", c]
    tofu(args, cwd=stack_dir)
    out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True)
    return json.loads(out)

def ecr_login(registry: str, region: str):
    pw = subprocess.check_output(["aws","ecr","get-login-password","--region",region], text=True)
    sh(["docker","login","--username","AWS","--password-stdin",registry], input_text=pw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()

    region = require("AWS_REGION")
    out = tofu_output_json("deploy-aws/shared/nondurable", args.env)

    app_repo_url   = out["ecr_app_url"]["value"]
    spark_repo_url = out["ecr_spark_url"]["value"]

    registry = app_repo_url.split("/")[0]
    ecr_login(registry, region)

    app_tag = require("APP_IMAGE_TAG")
    spark_tag = require("SPARK_IMAGE_TAG")
    platform = os.getenv("DOCKER_RUN_REMOTE_PLATFORM", "linux/amd64")

    # Build images
    sh(["docker","build","--platform",platform,"-t",f"{app_repo_url}:{app_tag}","core-app"])
    sh(["docker","build","--platform",platform,"-t",f"{spark_repo_url}:{spark_tag}","-f","core-app/analytics/docker/Dockerfile","core-app/analytics"])

    # Push images
    sh(["docker","push",f"{app_repo_url}:{app_tag}"])
    sh(["docker","push",f"{spark_repo_url}:{spark_tag}"])

    print("Pushed:")
    print("  ", f"{app_repo_url}:{app_tag}")
    print("  ", f"{spark_repo_url}:{spark_tag}")

if __name__ == "__main__":
    main()
