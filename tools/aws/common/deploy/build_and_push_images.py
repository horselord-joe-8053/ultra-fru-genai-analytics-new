
"""
Build and push ECR images for app and spark.

One-liners:
  python tools/aws/common/deploy/build_and_push_images.py --env dev

This tool:
- Reads ECR repository URLs from `live-deploy-aws/shared/nondurable` state
- Logs into ECR properly
- Builds and pushes images

Replace the build contexts to match your legacy project.
"""
import argparse, os, json, subprocess, sys, re, threading, time
from tools.common.env import load_dotenv, require, get_int_env
from tools.aws.common.core.terra_runner import get_terra_env
from tools.aws.common.core.backend import backend_config, resolve_region
from tools.common.logging import logger

load_dotenv()

BUILD_STEP_INTERVAL_SEC = int(os.getenv("BUILD_HEARTBEAT_INTERVAL_SEC", "30"))
# Per-step timeout (seconds). 0 = no timeout. Default 20 min; builds rarely exceed 15 min per image.
BUILD_STEP_TIMEOUT_SEC = int(os.getenv("BUILD_STEP_TIMEOUT_SEC", "1200"))
# Emit Docker layer progress: "Step 3/8: RUN npm install" when we see new steps. Set to 0 to disable.
BUILD_EMIT_LAYER_PROGRESS = os.getenv("BUILD_EMIT_LAYER_PROGRESS", "1") != "0"

def sh(cmd, input_text=None):
    logger.info(f"[RUN] {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, input=input_text, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"[FAILED] {' '.join(cmd)}: {e}")
        raise


# Docker --progress=plain emits lines like "#3 [2/8] RUN npm install" or "#1 [internal] load build definition"
_LAYER_STEP_RE = re.compile(r"^#(\d+)\s+\[(\d+)/(\d+)\]\s+(.+)$")
_LAYER_INTERNAL_RE = re.compile(r"^#(\d+)\s+\[(internal|external)\]\s+(.+)$")


def _run_docker_streaming(
    cmd: list,
    step_name: str,
    step_num: int,
    total_steps: int,
    is_build: bool,
) -> subprocess.CompletedProcess:
    """
    Run docker with streaming output. For builds: parse layer lines and emit
    "Step X/Y: ..." progress. Heartbeat runs in parallel. Timeout enforced.
    """
    desc = f"{step_name} ({step_num}/{total_steps})"
    logger.step(f"{desc}...")
    timeout = BUILD_STEP_TIMEOUT_SEC if BUILD_STEP_TIMEOUT_SEC > 0 else None
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    proc = subprocess.Popen(
        cmd,
        cwd=os.getcwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    elapsed_ref = [0]
    stop = threading.Event()

    def heartbeat():
        while not stop.is_set():
            if stop.wait(1):
                return
            elapsed_ref[0] += 1
            if elapsed_ref[0] % BUILD_STEP_INTERVAL_SEC == 0 and elapsed_ref[0] > 0:
                msg = f"[heartbeat] {desc} (elapsed: {elapsed_ref[0]}s)"
                if timeout:
                    msg += f" [timeout: {timeout}s]"
                logger.info(msg)

    def read_stream():
        last_step = (0, 0)
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            print(line, flush=True)
            if is_build and BUILD_EMIT_LAYER_PROGRESS:
                m = _LAYER_STEP_RE.match(line)
                if m:
                    layer, cur, total, step_desc = m.group(1), m.group(2), m.group(3), m.group(4).strip()
                    if (int(cur), int(total)) != last_step:
                        last_step = (int(cur), int(total))
                        logger.info(f"[build] Step {cur}/{total}: {step_desc}")
                else:
                    m2 = _LAYER_INTERNAL_RE.match(line)
                    if m2:
                        layer, kind, step_desc = m2.group(1), m2.group(2), m2.group(3).strip()
                        logger.info(f"[build] Layer {layer}: {kind} {step_desc}")

    t_heartbeat = threading.Thread(target=heartbeat, daemon=True)
    t_reader = threading.Thread(target=read_stream, daemon=True)
    t_heartbeat.start()
    t_reader.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        stop.set()
        t_heartbeat.join(timeout=2)
        t_reader.join(timeout=2)

    return subprocess.CompletedProcess(cmd, proc.returncode)


def run_docker_with_progress(cmd: list, step_name: str, step_num: int, total_steps: int):
    """Run docker command with streaming output, layer progress, heartbeat, and optional timeout."""
    is_build = "build" in cmd
    proc = _run_docker_streaming(cmd, step_name, step_num, total_steps, is_build)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    logger.success(f"{step_name} done")

def tofu_output_json(stack_dir: str, env: str, region: str | None = None):
    logger.info(f"[TOFU OUTPUT] Getting outputs from {stack_dir}")
    try:
        cfg = backend_config(stack_dir, env, region)
        args = ["init","-upgrade","-reconfigure"]
        for c in cfg:
            args += ["-backend-config", c]
        subprocess.run([os.getenv("FRU_TF_BIN","tofu")] + args, cwd=stack_dir, check=True, env=get_terra_env(region))
        out = subprocess.check_output([os.getenv("FRU_TF_BIN","tofu"),"output","-json"], cwd=stack_dir, text=True, timeout=30, env=get_terra_env(region))
        result = json.loads(out)
        logger.success(f"[TOFU OUTPUT OK] {stack_dir}")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"[TOFU OUTPUT TIMEOUT] {stack_dir}")
        raise SystemExit(f"Tofu output timed out for {stack_dir}")
    except Exception as e:
        logger.error(f"[TOFU OUTPUT ERROR] {stack_dir}: {e}")
        raise

def _docker_basic_timeout() -> int | None:
    """Timeout for quick docker commands (login, info). 0 = no timeout."""
    sec = get_int_env("DOCKER_BASIC_CMD_TIMEOUT", 180)
    return sec if sec > 0 else None


def _docker_hung_suggestion() -> str:
    return (
        "\n"
        "Docker daemon may be hung or unresponsive. To recover:\n"
        "  ./tools/common/docker/docker-unstick-desktop-start.sh\n"
        "\n"
        "Run from the project root. Requires sudo for vmnetd. Then retry your command."
    )


def ecr_login(registry: str, region: str):
    logger.info(f"[ECR LOGIN] Logging in to {registry}")
    timeout = _docker_basic_timeout()
    try:
        pw = subprocess.check_output(["aws","ecr","get-login-password","--region",region], text=True, timeout=10)
        logger.info(f"[RUN] docker login --username AWS --password-stdin {registry}")
        subprocess.run(
            ["docker","login","--username","AWS","--password-stdin",registry],
            input=pw,
            text=True,
            check=True,
            timeout=timeout,
        )
        logger.success("[ECR LOGIN OK]")
    except subprocess.TimeoutExpired as e:
        logger.error(f"[ECR LOGIN TIMEOUT] docker login did not complete within {e.timeout}s")
        logger.error("This usually means the Docker daemon is hung or unresponsive.")
        logger.error(_docker_hung_suggestion())
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"[ECR LOGIN FAILED] {e}")
        raise
    except Exception as e:
        logger.error(f"[ECR LOGIN ERROR] {e}")
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("FRU_ENV","dev"))
    ap.add_argument("--region", default=None, help="Region (default: CLOUD_REGION)")
    ap.add_argument("--no-cache", action="store_true", help="Build Spark image without cache (ensures fresh run_analytics.py)")
    args = ap.parse_args()

    region = resolve_region(args.region)
    os.environ["CLOUD_REGION"] = region
    os.environ["AWS_REGION"] = region

    logger.step("Building and pushing Docker images")
    logger.info(f"[BUILD] Region: {region}")
    
    logger.info("[BUILD] Getting ECR URLs from terraform state...")
    out = tofu_output_json("live-deploy-aws/shared/nondurable", args.env, region)

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

    # Build and push with per-step progress (1/4, 2/4, etc.) and heartbeat so we know which step and elapsed time
    # --progress=plain for line-by-line output; avoids silent buffering in Cursor/CI
    run_docker_with_progress(
        ["docker","build","--progress=plain","--platform",platform,"-t",f"{app_repo_url}:{app_tag}","core-app"],
        "Building app image", 1, 4,
    )
    spark_build_cmd = ["docker","build","--progress=plain","--platform",platform,"-t",f"{spark_repo_url}:{spark_tag}","-f","core-app/analytics/docker/Dockerfile","core-app"]
    if args.no_cache:
        spark_build_cmd.insert(2, "--no-cache")
        logger.info("[BUILD] Spark: --no-cache (fresh build)")
    run_docker_with_progress(
        spark_build_cmd,
        "Building spark image", 2, 4,
    )
    run_docker_with_progress(
        ["docker","push",f"{app_repo_url}:{app_tag}"],
        "Pushing app image", 3, 4,
    )
    run_docker_with_progress(
        ["docker","push",f"{spark_repo_url}:{spark_tag}"],
        "Pushing spark image", 4, 4,
    )

    logger.success("All images pushed:")
    print("  ", f"{app_repo_url}:{app_tag}")
    print("  ", f"{spark_repo_url}:{spark_tag}")
    
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as e:
        logger.error(f"Build step timed out after {e.timeout}s: {e.cmd}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build and push failed: {e}")
        sys.exit(1)
