"""
Pre-destroy for GCP durable stack: wait for Cloud SQL async deletion before full destroy.

Cloud SQL deletion is asynchronous. GCP can take 5–15+ minutes to fully release the
service networking connection. Terraform proceeds immediately after issuing the delete,
so the connection delete fails with: "Producer services (e.g. CloudSQL) are still
using this connection."

Targets (durable main.tf):
- module.cloud_sql: Cloud SQL instance (google_sql_database_instance) + database
- google_service_networking_connection.default: VPC peering to servicenetworking (for Cloud SQL private IP)
  (Not google_vpc_access_connector.cloud_run, which is for Cloud Run→VPC.)

Strategy (mirrors AWS kube_pre_destroy + teardown_orphan_cleanup):
1. Run targeted destroy of module.cloud_sql only.
2. Poll gcloud until the instance is gone (describe returns 404).
3. Delete service networking peering via gcloud compute (Compute API). Then state rm.
4. Then run full durable destroy; alloc/VPC can be removed cleanly.

Why gcloud compute networks peerings delete (not tofu or gcloud services vpc-peerings):
- tofu destroy -target=google_service_networking_connection.default and gcloud services
  vpc-peerings delete both use the Service Networking API. That API enforces a check that
  no producer services (Cloud SQL, Memorystore, etc.) are still using the connection.
- GCP's backend can take 10–30+ minutes (or longer) to release this after Cloud SQL is
  deleted. The Service Networking API fails with "Producer services still using" until
  then, requiring long polling or retries.
- gcloud compute networks peerings delete uses the Compute API (networks.removePeering),
  the same path as the VPC Network Peering Console UI. It removes the peering from the
  consumer's network side and succeeds immediately, bypassing the producer check.
- Both paths delete the same underlying peering; we then state rm so Terraform stays in sync.

Reference: docs/learned/KUBE_INGRESS_LEARNED.md §0.7 (LB delete → ENI release → SG delete).
"""
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.cloud_shared.stats import TeardownStats

# Cloud SQL async delete can take 5–15+ min. Poll up to 20 min with 60s heartbeat.
CLOUD_SQL_WAIT_TIMEOUT_SEC = int(os.environ.get("GCP_CLOUD_SQL_WAIT_TIMEOUT_SEC", "1200"))
CLOUD_SQL_POLL_INTERVAL_SEC = int(os.environ.get("GCP_CLOUD_SQL_POLL_INTERVAL_SEC", "30"))
# Fallback: retry full durable destroy on connection error (if connection wasn't in state to target).
CONNECTION_RETRY_WAIT_SEC = int(os.environ.get("GCP_CONNECTION_RETRY_WAIT_SEC", "120"))
CONNECTION_RETRY_MAX = int(os.environ.get("GCP_CONNECTION_RETRY_MAX", "15"))


def pre_destroy_durable(
    env: str,
    region: str,
    stack_path: str,
    destroy_vars: list[str],
    stats: "TeardownStats | None" = None,
) -> None:
    """
    Pre-destroy durable: targeted Cloud SQL destroy + poll until instance gone.

    Call before running full `tofu destroy` on the durable stack. Idempotent: if
    Cloud SQL is not in state or already gone, skips or no-ops gracefully.
    """
    from tools.cloud_shared.logging import logger
    from tools.gcp.scope_shared.core import resource_names
    from tools.gcp.scope_shared.core.terra_runner import terra_capture
    from tools.cloud_shared.retry import poll_until

    instance_name = resource_names.cloud_sql_instance(env)
    gcp_project = os.getenv("GCP_PROJECT_ID", "").strip()
    if not gcp_project:
        logger.warning("Pre-destroy durable: GCP_PROJECT_ID not set; skipping Cloud SQL wait.")
        return

    def _log_result(target: str, rc: int, err: str, max_len: int = 120):
        """Log cmd result: rc and brief error snippet."""
        if rc == 0:
            logger.info(f"Pre-destroy durable: {target} -> rc=0 (ok)")
        else:
            snippet = (err or "").strip()[:max_len].replace("\n", " ")
            logger.info(f"Pre-destroy durable: {target} -> rc={rc}: {snippet}")

    def _timed(component: str, identifier: str, fn):
        if stats:
            with stats.timed(component, identifier):
                fn()
        else:
            fn()

    def _run_targeted_destroy():
        """Destroy module.cloud_sql only (Cloud SQL instance + db). Terraform removes from state; GCP deletes async."""
        cmd = ["destroy", "-target=module.cloud_sql", "-auto-approve"] + destroy_vars
        logger.info("Pre-destroy durable: tofu destroy -target=module.cloud_sql (Cloud SQL instance + db)")
        result = terra_capture(cmd, cwd=stack_path, region=region)
        err = (result.stderr or result.stdout or "")
        _log_result("module.cloud_sql", result.returncode, err)
        # No-op if Cloud SQL not in state (e.g. already destroyed, or durable never applied).
        if result.returncode != 0:
            if "no matching resources" in err.lower() or "no state" in err.lower():
                logger.info("Pre-destroy durable: Cloud SQL not in state; skipping wait.")
                return
            # Real error: propagate
            raise RuntimeError(f"Targeted Cloud SQL destroy failed: {err}")

    def _instance_gone() -> bool:
        """Return True when Cloud SQL instance is no longer present (gcloud describe 404)."""
        r = subprocess.run(
            [
                "gcloud", "sql", "instances", "describe", instance_name,
                "--project", gcp_project,
                "--format", "value(name)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # rc!=0 means NOT_FOUND or error -> treat as gone
        return r.returncode != 0

    logger.step(
        "Pre-destroy durable: targeted Cloud SQL destroy, then polling until instance gone "
        "(GCP async delete 5–15+ min)..."
    )

    _timed("Cloud SQL (targeted destroy)", instance_name, _run_targeted_destroy)

    # Poll until instance is gone. If targeted destroy was a no-op (not in state), instance
    # may already be gone or never existed; poll_until will succeed quickly.
    def _wait_for_gone():
        ok = poll_until(
            _instance_gone,
            timeout_sec=CLOUD_SQL_WAIT_TIMEOUT_SEC,
            check_interval_sec=CLOUD_SQL_POLL_INTERVAL_SEC,
            heartbeat_interval_sec=60,
            heartbeat_message_fn=lambda elapsed: (
                f"Pre-destroy durable: waiting for Cloud SQL {instance_name} to be gone "
                f"(GCP async delete) ... ({elapsed}s)"
            ),
        )
        if not ok:
            raise TimeoutError(
                f"Cloud SQL {instance_name} still present after {CLOUD_SQL_WAIT_TIMEOUT_SEC}s. "
                "GCP async delete may take longer; retry teardown or wait manually."
            )

    _timed("Cloud SQL (wait for gone)", instance_name, _wait_for_gone)
    logger.info(f"Pre-destroy durable: gcloud sql instances describe {instance_name} -> instance gone (rc!=0)")

    # Delete service networking peering via gcloud compute (Compute API).
    # Uses Compute API (networks.removePeering), not Service Networking API. The latter fails
    # with "Producer services still using" for 10–30+ min after Cloud SQL is gone; Compute API
    # succeeds immediately (same as VPC Network Peering Console Delete).
    def _delete_connection_via_gcloud():
        network_name = resource_names.durable_network_name(env)
        peering_name = "servicenetworking-googleapis-com"
        logger.info(
            f"Pre-destroy durable: gcloud compute networks peerings delete {peering_name} "
            f"--network={network_name} (Compute API, avoids long Service Networking poll)"
        )
        r = subprocess.run(
            [
                "gcloud", "compute", "networks", "peerings", "delete", peering_name,
                "--network", network_name,
                "--project", gcp_project,
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        err = (r.stderr or r.stdout or "").strip()
        _log_result(f"gcloud peerings delete {peering_name}", r.returncode, err)
        if r.returncode == 0:
            logger.info("Pre-destroy durable: service networking peering deleted via gcloud.")
        elif any(
            p in err.lower()
            for p in ("not found", "does not exist", "could not find", "there is no peering")
        ):
            logger.info("Pre-destroy durable: peering already gone; continuing.")
        else:
            raise RuntimeError(f"gcloud peerings delete failed: {err}")

        # Remove from Terraform state so full destroy doesn't try to delete (resource already
        # gone in GCP). Terraform would otherwise attempt Service Networking API delete and fail.
        logger.info("Pre-destroy durable: tofu state rm google_service_networking_connection.default")
        from tools.gcp.scope_shared.core.terra_runner import get_terra_env
        exe = os.getenv("FRU_TF_BIN", "tofu")
        rm_r = subprocess.run(
            [exe, "state", "rm", "google_service_networking_connection.default"],
            cwd=stack_path,
            capture_output=True,
            text=True,
            timeout=30,
            env=get_terra_env(region),
        )
        stderr_lower = (rm_r.stderr or rm_r.stdout or "").lower()
        if rm_r.returncode != 0 and not any(
            p in stderr_lower for p in ("not in state", "no instance", "resource not found", "could not find")
        ):
            logger.warning(f"Pre-destroy durable: state rm rc={rm_r.returncode}: {(rm_r.stderr or rm_r.stdout or '')[:80]}")
        else:
            logger.info("Pre-destroy durable: connection removed from state.")

    _timed("Connection (gcloud peerings delete)", "service_networking", _delete_connection_via_gcloud)
    logger.info("Pre-destroy durable: Cloud SQL gone, connection deleted; proceeding to full durable destroy.")


def destroy_durable_with_retry(
    destroy_cmd: list[str],
    stack_path: str,
    region: str,
) -> None:
    """
    Run tofu destroy on durable stack; retry on "Producer services still using connection".

    Fallback when connection wasn't in state for pre-destroy targeted destroy.
    GCP can take 10–30+ min to release the connection after Cloud SQL is gone.
    """
    from tools.cloud_shared.logging import logger
    from tools.gcp.scope_shared.core.terra_runner import terra_capture
    from tools.cloud_shared.retry import sleep_with_heartbeat

    err_pattern = "producer services"
    for attempt in range(1, CONNECTION_RETRY_MAX + 1):
        logger.info(f"Durable destroy: tofu destroy (full stack) attempt {attempt}/{CONNECTION_RETRY_MAX}")
        result = terra_capture(destroy_cmd, cwd=stack_path, region=region)
        err = (result.stderr or result.stdout or "")
        logger.info(f"Durable destroy: rc={result.returncode}" + (f": {(err or '')[:100].replace(chr(10), ' ')}" if result.returncode != 0 else " (ok)"))
        if result.returncode == 0:
            return
        err_lower = err.lower()
        if err_pattern in err_lower and "still using" in err_lower:
            if attempt < CONNECTION_RETRY_MAX:
                logger.info(
                    f"Durable destroy failed (connection still in use); retrying in {CONNECTION_RETRY_WAIT_SEC}s "
                    f"(attempt {attempt}/{CONNECTION_RETRY_MAX})..."
                )
                sleep_with_heartbeat(
                    CONNECTION_RETRY_WAIT_SEC,
                    "Durable destroy retry: waiting for GCP to release connection",
                    interval_sec=60,
                )
                continue
        # Non-retriable or max retries exceeded: propagate
        raise RuntimeError(f"Durable destroy failed after {attempt} attempt(s): {err}")
