"""
Shared Docker build utilities. Used by AWS (ECR) and GCP (Artifact Registry) build scripts.

- run_docker_with_progress: Docker build/push with streaming, heartbeat, timeout
- sh: Run command with logging
- remove_old_local_images_after_build: Prune dangling images
- untag_registry_refs_after_push: Remove registry tags locally after push
"""
import os
import re
import subprocess
import threading

from tools.cloud_shared.env import get_int_env
from tools.cloud_shared.logging import logger

BUILD_STEP_INTERVAL_SEC = int(os.getenv("BUILD_HEARTBEAT_INTERVAL_SEC", "30"))
BUILD_STEP_TIMEOUT_SEC = int(os.getenv("BUILD_STEP_TIMEOUT_SEC", "1200"))
BUILD_EMIT_LAYER_PROGRESS = os.getenv("BUILD_EMIT_LAYER_PROGRESS", "1") != "0"

_LAYER_STEP_RE = re.compile(r"^#(\d+)\s+\[(\d+)/(\d+)\]\s+(.+)$")
_LAYER_INTERNAL_RE = re.compile(r"^#(\d+)\s+\[(internal|external)\]\s+(.+)$")


def sh(cmd: list, input_text: str | None = None):
    """Run command with logging. Raises on non-zero exit."""
    logger.info(f"[RUN] {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, input=input_text, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"[FAILED] {' '.join(cmd)}: {e}")
        raise


def _run_docker_streaming(
    cmd: list,
    step_name: str,
    step_num: int,
    total_steps: int,
    is_build: bool,
) -> subprocess.CompletedProcess:
    """Run docker with streaming output, layer progress, heartbeat, timeout."""
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
                    cur, total, step_desc = m.group(2), m.group(3), m.group(4).strip()
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
    """Run docker command with streaming output, layer progress, heartbeat, timeout."""
    is_build = "build" in cmd
    proc = _run_docker_streaming(cmd, step_name, step_num, total_steps, is_build)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    logger.success(f"{step_name} done")


def remove_old_local_images_after_build() -> None:
    """Remove dangling local images after successful build. Non-fatal."""
    logger.info("[BUILD] Removing old local images (dangling from previous build)...")
    try:
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, Exception):
        pass


def untag_registry_refs_after_push(
    app_repo_url: str,
    spark_repo_url: str,
    app_tag: str,
    spark_tag: str,
    *,
    app_canonical_name: str | None = None,
    spark_canonical_name: str | None = None,
) -> None:
    """
    Remove registry tags from local Docker after successful push.
    Keeps only canonical names (e.g. fru-api-img-dev:latest) for multi-region push.
    app_repo_url/spark_repo_url: full refs to remove (e.g. registry/repo or registry/repo/image).
    app_canonical_name/spark_canonical_name: optional; for GCP Artifact Registry (repo/image),
      pass the repo names so "keeping X:latest" is correct.
    """
    refs: list[str] = []
    if app_tag == "latest":
        refs.append(f"{app_repo_url}:latest")
    else:
        refs.extend([f"{app_repo_url}:{app_tag}", f"{app_repo_url}:latest"])
    if spark_tag == "latest":
        refs.append(f"{spark_repo_url}:latest")
    else:
        refs.extend([f"{spark_repo_url}:{spark_tag}", f"{spark_repo_url}:latest"])
    refs = list(dict.fromkeys(refs))

    app_repo_name = app_canonical_name or app_repo_url.split("/")[-1]
    spark_repo_name = spark_canonical_name or spark_repo_url.split("/")[-1]

    logger.info(
        f"[UNTAG] Removing registry tags locally; "
        f"keeping {app_repo_name}:latest, {spark_repo_name}:latest"
    )
    removed = 0
    for ref in refs:
        try:
            result = subprocess.run(
                ["docker", "rmi", ref],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                removed += 1
        except (subprocess.TimeoutExpired, Exception):
            pass
    if removed > 0:
        logger.success(f"[UNTAG] Removed {removed} registry tag(s) locally")


def docker_basic_timeout() -> int | None:
    """Timeout for quick docker commands (login, info). 0 = no timeout."""
    sec = get_int_env("DOCKER_BASIC_CMD_TIMEOUT", 180)
    return sec if sec > 0 else None


def docker_hung_suggestion() -> str:
    return (
        "\n"
        "Docker daemon may be hung or unresponsive. To recover:\n"
        "  ./tools/cloud_shared/docker/docker-unstick-desktop-start.sh\n"
        "\n"
        "Run from the project root. Requires sudo for vmnetd. Then retry your command."
    )
