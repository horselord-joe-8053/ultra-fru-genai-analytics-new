"""
Local Docker Desktop Kubernetes helpers.

Prerequisites: Docker Desktop running with Kubernetes enabled (Settings → Kubernetes).
Used by local deploy, kube_apply, and verify for scope=kube.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tools.cloud_shared.logging import logger

K8S_NAMESPACE = "fru-kube"
API_SERVICE = "fru-api-svc"
DESKTOP_SETTINGS = Path.home() / "Library/Group Containers/group.com.docker/settings-store.json"
PORT_FORWARD_PID_FILE = "kube-api-port-forward.pid"


def _run(cmd: list[str], *, check: bool = True, capture: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=check,
    )


def desktop_kubernetes_status() -> dict[str, str]:
    """Parse `docker desktop kubernetes status` (State, Version, etc.)."""
    try:
        r = _run(["docker", "desktop", "kubernetes", "status"], check=False, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"State": "unknown", "Error": "docker desktop CLI unavailable"}
    if r.returncode != 0:
        return {"State": "unknown", "Error": (r.stderr or r.stdout or "").strip()}
    out: dict[str, str] = {}
    for line in (r.stdout or "").splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            out[key.strip()] = val.strip()
    return out


def is_desktop_kubernetes_running() -> bool:
    state = desktop_kubernetes_status().get("State", "").lower()
    return state in ("running", "started")


def enable_desktop_kubernetes(*, restart: bool = True, wait_timeout_sec: int = 300) -> None:
    """
    Enable Kubernetes in Docker Desktop settings and optionally restart Docker.
    macOS only (settings-store.json path).
    """
    if not DESKTOP_SETTINGS.is_file():
        raise RuntimeError(
            f"Docker Desktop settings not found at {DESKTOP_SETTINGS}. "
            "Enable Kubernetes manually: Docker Desktop → Settings → Kubernetes → Enable."
        )
    data = json.loads(DESKTOP_SETTINGS.read_text(encoding="utf-8"))
    if not data.get("KubernetesEnabled"):
        logger.info("Enabling Kubernetes in Docker Desktop settings...")
        data["KubernetesEnabled"] = True
        DESKTOP_SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if restart:
        logger.info("Restarting Docker Desktop to start Kubernetes (may take 1–3 min)...")
        _run(["docker", "desktop", "restart"], capture=False, check=False, timeout=60)
        time.sleep(15)
    deadline = time.time() + wait_timeout_sec
    while time.time() < deadline:
        if is_desktop_kubernetes_running():
            logger.success("Docker Desktop Kubernetes is running")
            return
        time.sleep(5)
    raise RuntimeError(
        "Kubernetes did not reach running state within timeout. "
        "Open Docker Desktop → Settings → Kubernetes and confirm it is enabled."
    )


def ensure_local_kubectl_context() -> str:
    """
    Select docker-desktop / kind / minikube context via tools/standalone/kubeconfig.py.
    Returns the active context name.
    """
    script = os.path.join(_repo_root, "tools", "standalone", "kubeconfig.py")
    r = subprocess.run(
        [sys.executable, script, "--provider", "local", "--env", "dev"],
        cwd=_repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(
            (r.stderr or r.stdout or "kubectl context setup failed").strip()
            + "\nEnable Kubernetes: Docker Desktop → Settings → Kubernetes → Enable."
        )
    ctx = subprocess.run(
        ["kubectl", "config", "current-context"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    name = (ctx.stdout or "").strip()
    if not name:
        raise RuntimeError("No kubectl current-context after local kubeconfig setup.")
    logger.info(f"kubectl context: {name}")
    return name


def require_desktop_kubernetes(*, auto_enable: bool | None = None) -> None:
    """
    Fail fast if Docker Desktop Kubernetes is not running.
    auto_enable: when True, toggles settings and restarts Docker; default from FRU_AUTO_ENABLE_DESKTOP_K8S.
    """
    if is_desktop_kubernetes_running():
        return
    if auto_enable is None:
        auto_enable = os.environ.get("FRU_AUTO_ENABLE_DESKTOP_K8S", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
    if auto_enable:
        enable_desktop_kubernetes()
        return
    status = desktop_kubernetes_status()
    raise RuntimeError(
        "Docker Desktop Kubernetes is not running "
        f"(state={status.get('State', 'unknown')}). "
        "Enable it: Docker Desktop → Settings → Kubernetes → Enable, then retry. "
        "Or set FRU_AUTO_ENABLE_DESKTOP_K8S=1 for deploy to enable automatically."
    )


def import_image_to_desktop_k8s(image: str) -> bool:
    """Import a local docker image tag into Docker Desktop k8s containerd."""
    check = subprocess.run(["docker", "inspect", "desktop-control-plane"], capture_output=True)
    if check.returncode != 0:
        logger.warning(f"desktop-control-plane not found; skipping k8s image import for {image}")
        return False
    inspect = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if inspect.returncode != 0:
        logger.warning(f"Image {image} not found on host; build before kube deploy")
        return False
    logger.info(f"Importing {image} into Docker Desktop Kubernetes node...")
    proc = subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE)
    import_proc = subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            "desktop-control-plane",
            "ctr",
            "-n",
            "k8s.io",
            "images",
            "import",
            "-",
        ],
        stdin=proc.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.stdout:
        proc.stdout.close()
    _, err = import_proc.communicate()
    if import_proc.returncode != 0:
        logger.warning(
            f"k8s image import failed for {image}: {err.decode(errors='replace')[:300]}"
        )
        return False
    logger.success(f"Imported {image} into k8s node")
    return True


def _memo_dir() -> Path:
    from tools.local.scope_shared.local_deploy_config import get_memo_dir

    return Path(get_memo_dir())


def stop_kube_api_port_forward() -> None:
    pid_file = _memo_dir() / PORT_FORWARD_PID_FILE
    if not pid_file.is_file():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, 15)
    except (OSError, ValueError):
        pass
    pid_file.unlink(missing_ok=True)


def start_kube_api_port_forward(local_port: int = 30080) -> None:
    """Background kubectl port-forward svc/fru-api-svc local_port:80 (NodePort fallback on Docker Desktop)."""
    stop_kube_api_port_forward()
    cmd = [
        "kubectl",
        "port-forward",
        "-n",
        K8S_NAMESPACE,
        f"svc/{API_SERVICE}",
        f"{local_port}:80",
    ]
    log_path = _memo_dir() / "kube-api-port-forward.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (_memo_dir() / PORT_FORWARD_PID_FILE).write_text(str(proc.pid), encoding="utf-8")
    logger.info(
        f"Started kubectl port-forward {API_SERVICE} → localhost:{local_port} (pid {proc.pid})"
    )


def _health_ok(base_url: str, timeout_sec: float = 3.0) -> bool:
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def ensure_kube_api_reachable(api_port: int = 30080, wait_timeout_sec: int = 120) -> str:
    """
    Ensure kube API responds on localhost:api_port.
    Tries NodePort first; starts kubectl port-forward if connection refused (common on Docker Desktop Mac).
    Returns base URL (http://localhost:{port}).
    """
    base = f"http://localhost:{api_port}"
    deadline = time.time() + wait_timeout_sec
    while time.time() < deadline:
        if _health_ok(base):
            return base
        time.sleep(3)

    logger.warning(
        f"NodePort http://localhost:{api_port}/health not reachable; starting kubectl port-forward..."
    )
    start_kube_api_port_forward(api_port)
    deadline = time.time() + wait_timeout_sec
    while time.time() < deadline:
        if _health_ok(base):
            logger.success(f"Kube API reachable via port-forward at {base}")
            return base
        time.sleep(3)

    raise RuntimeError(
        f"Kube API not reachable at {base}/health after {wait_timeout_sec}s. "
        f"Check: kubectl get pods -n {K8S_NAMESPACE}"
    )


def ensure_delta_host_path() -> None:
    """Ensure /tmp/fru-delta on the k8s node is writable by Spark (UID 1001)."""
    check = subprocess.run(["docker", "inspect", "desktop-control-plane"], capture_output=True)
    if check.returncode != 0:
        return
    for cmd in (
        ["docker", "exec", "desktop-control-plane", "mkdir", "-p", "/tmp/fru-delta"],
        ["docker", "exec", "desktop-control-plane", "chmod", "777", "/tmp/fru-delta"],
    ):
        subprocess.run(cmd, capture_output=True, timeout=30)


def prepare_local_kube(
    *,
    skip_spark: bool = False,
    import_images: tuple[str, ...] | None = None,
) -> str:
    """
    Full local-kube preflight: K8s running, kubectl context, optional image import.
    Returns kubectl context name.
    """
    require_desktop_kubernetes()
    ctx = ensure_local_kubectl_context()
    ensure_delta_host_path()
    if import_images is None:
        import_images = ("fru-api:local",) if skip_spark else ("fru-api:local", "fru-spark:local")
    for image in import_images:
        import_image_to_desktop_k8s(image)
    return ctx
