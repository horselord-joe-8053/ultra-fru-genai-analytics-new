
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
import argparse, os, json, subprocess, sys
from tools._env import load_dotenv, require
from tools.tofu_runner import tofu
from tools.aws._backend import backend_config
from tools import logger

load_dotenv()

def sh(cmd, input_text=None):
    logger.info(f"[RUN] {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, input=input_text, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"[FAILED] {' '.join(cmd)}: {e}")
        raise

def tofu_output_json(stack_dir: str, env: str):
    logger.info(f"[TOFU OUTPUT] Getting outputs from {stack_dir}")
    try:
        cfg = backend_config(os.path.basename(stack_dir), env)
        args = ["init","-upgrade"]
        for c in cfg:
            args += ["-backend-config", c]
        tofu(args, cwd=stack_dir)
        out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True, timeout=30)
        result = json.loads(out)
        logger.success(f"[TOFU OUTPUT OK] {stack_dir}")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"[TOFU OUTPUT TIMEOUT] {stack_dir}")
        raise SystemExit(f"Tofu output timed out for {stack_dir}")
    except Exception as e:
        logger.error(f"[TOFU OUTPUT ERROR] {stack_dir}: {e}")
        raise

def ecr_login(registry: str, region: str):
    logger.info(f"[ECR LOGIN] Logging in to {registry}")
    try:
        pw = subprocess.check_output(["aws","ecr","get-login-password","--region",region], text=True, timeout=10)
        sh(["docker","login","--username","AWS","--password-stdin",registry], input_text=pw)
        logger.success("[ECR LOGIN OK]")
    except subprocess.TimeoutExpired:
        logger.error("[ECR LOGIN TIMEOUT]")
        raise SystemExit("ECR login timed out")
    except Exception as e:
        logger.error(f"[ECR LOGIN ERROR] {e}")
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    args = ap.parse_args()

    logger.step("Building and pushing Docker images")

    region = require("AWS_REGION")
    logger.info(f"[BUILD] Region: {region}")
    
    logger.info("[BUILD] Getting ECR URLs from terraform state...")
    out = tofu_output_json("deploy-aws/shared/nondurable", args.env)

    app_repo_url   = out["ecr_app_url"]["value"]
    spark_repo_url = out["ecr_spark_url"]["value"]
    
    logger.info(f"[BUILD] App repo: {app_repo_url}")
    logger.info(f"[BUILD] Spark repo: {spark_repo_url}")

    registry = app_repo_url.split("/")[0]
    
    logger.info("[BUILD] Logging in to ECR...")
    ecr_login(registry, region)

    app_tag = require("APP_IMAGE_TAG")
    spark_tag = require("SPARK_IMAGE_TAG")
    platform = os.getenv("DOCKER_RUN_REMOTE_PLATFORM", "linux/amd64")
    
    logger.info(f"[BUILD] Platform: {platform}")
    logger.info(f"[BUILD] App tag: {app_tag}")
    logger.info(f"[BUILD] Spark tag: {spark_tag}")

    # Build images
    logger.step("Building app image...")
    sh(["docker","build","--platform",platform,"-t",f"{app_repo_url}:{app_tag}","core-app"])
    logger.success("App image built")
    
    logger.step("Building spark image...")
    sh(["docker","build","--platform",platform,"-t",f"{spark_repo_url}:{spark_tag}","-f","core-app/analytics/docker/Dockerfile","core-app/analytics"])
    logger.success("Spark image built")

    # Push images
    logger.step("Pushing app image...")
    sh(["docker","push",f"{app_repo_url}:{app_tag}"])
    logger.success("App image pushed")
    
    logger.step("Pushing spark image...")
    sh(["docker","push",f"{spark_repo_url}:{spark_tag}"])
    logger.success("Spark image pushed")

    logger.success("All images pushed:")
    print("  ", f"{app_repo_url}:{app_tag}")
    print("  ", f"{spark_repo_url}:{spark_tag}")
    
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Build and push failed: {e}")
        sys.exit(1)
