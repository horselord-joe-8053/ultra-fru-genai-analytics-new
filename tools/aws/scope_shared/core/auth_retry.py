"""
AWS auth-error retry with clock sync.

=============================================================================
ORIGIN (actual errors seen during deployment - Feb 2026)
=============================================================================
  - SignatureDoesNotMatch: Signature expired
  - AuthFailure: AWS was not able to validate the provided access credentials

These occurred during CloudFront re-apply in a long us-east-2 deploy (scope=all).
AWS request signatures include a timestamp; if the system clock is off by >15 min
or a request is queued too long, AWS rejects with "Signature expired".

=============================================================================
PURPOSE
=============================================================================
Retry failed tofu/terraform subprocess calls when AWS returns auth errors.
Before each retry: sync system clock via NTP (sntp -sS time.apple.com).
This often resolves clock-skew-induced "Signature expired" without manual intervention.

=============================================================================
USAGE (minimal footprint in caller)
=============================================================================
  result = run_with_auth_retry(lambda: subprocess.run(cmd, ...))

The runner callable must return a CompletedProcess. Config via .env:
  AUTH_REFRESH_FAILURE_RETRY_WAIT_TIME=30  # seconds between retries
  MAX_AUTH_REFRESH_FAILURE_RETRY=3          # max retries after initial failure
"""
import os
import shutil
import subprocess
import time
from typing import Callable, TypeVar

from tools.cloud_shared.logging import logger

T = TypeVar("T")

# Substrings in stderr/stdout that indicate AWS auth/signature failures.
# Sourced from actual deployment errors (SignatureDoesNotMatch, AuthFailure).
_AUTH_ERROR_PATTERNS = (
    "SignatureDoesNotMatch",
    "Signature expired",
    "AuthFailure",
    "AWS was not able to validate the provided access credentials",
    "InvalidSignatureException",
)


def _get_wait_sec() -> int:
    """Seconds to wait between retries. Default 30."""
    return int(os.environ.get("AUTH_REFRESH_FAILURE_RETRY_WAIT_TIME", "30"))


def _get_max_retries() -> int:
    """Max retry attempts after initial failure. Default 3."""
    return int(os.environ.get("MAX_AUTH_REFRESH_FAILURE_RETRY", "3"))


def _is_auth_error(result: subprocess.CompletedProcess) -> bool:
    """
    True if stderr/stdout contain known AWS auth error patterns.
    Cites the actual errors we saw: SignatureDoesNotMatch, AuthFailure.
    """
    combined = f"{result.stderr or ''}\n{result.stdout or ''}"
    return any(p in combined for p in _AUTH_ERROR_PATTERNS)


def _sync_clock() -> bool:
    """
    Sync system clock via NTP. Uses sntp -sS time.apple.com (macOS).
    -sS: set system time (requires root on some systems; macOS allows it).
    Clock skew is a common cause of "Signature expired" (AWS rejects if
    request timestamp is outside ±15 min window).
    Returns True if sync succeeded, False if sntp missing or sync failed.
    """
    sntp = shutil.which("sntp")
    if not sntp:
        logger.warning("[auth_retry] sntp not found; skipping clock sync")
        return False
    try:
        subprocess.run(
            [sntp, "-sS", "time.apple.com"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        logger.info("[auth_retry] Clock synced via sntp time.apple.com")
        return True
    except Exception as e:
        logger.warning(f"[auth_retry] Clock sync failed: {e}")
        return False


def run_with_auth_retry(runner_fn: Callable[[], T]) -> T:
    """
    Run runner_fn(). On AWS auth errors, sync clock and retry.

    runner_fn must be a no-arg callable returning subprocess.CompletedProcess
    (with .returncode, .stdout, .stderr). Used to wrap tofu/terraform subprocess.

    Minimal footprint: run_with_auth_retry(lambda: subprocess.run(...))

    Config from .env:
      AUTH_REFRESH_FAILURE_RETRY_WAIT_TIME=30  # seconds between retries
      MAX_AUTH_REFRESH_FAILURE_RETRY=3         # max retry attempts
    """
    max_retries = _get_max_retries()
    wait_sec = _get_wait_sec()

    last_result: T | None = None
    for attempt in range(max_retries + 1):
        last_result = runner_fn()

        # CompletedProcess: check returncode and stderr
        if hasattr(last_result, "returncode") and hasattr(last_result, "stderr"):
            proc = last_result
            if proc.returncode == 0:
                if attempt > 0:
                    logger.info(
                        f"[auth_retry] *** AUTH RETRY FLOW *** Succeeded on attempt {attempt + 1}"
                    )
                return last_result
            if not _is_auth_error(proc):
                # Not an auth error; don't retry
                return last_result
            if attempt < max_retries:
                logger.warning("")
                logger.warning(
                    "[auth_retry] *** AUTH RETRY FLOW *** "
                    f"Attempt {attempt + 1}/{max_retries + 1} failed with SignatureDoesNotMatch/AuthFailure"
                )
                logger.warning(
                    f"[auth_retry] Syncing clock via NTP, waiting {wait_sec}s, then retrying..."
                )
                _sync_clock()
                logger.info(f"[auth_retry] Waiting {wait_sec}s before retry...")
                time.sleep(wait_sec)
                logger.info(f"[auth_retry] Retrying (attempt {attempt + 2}/{max_retries + 1})...")
                logger.warning("")
            else:
                logger.warning("")
                logger.warning(
                    "[auth_retry] *** AUTH RETRY FLOW *** Max retries reached; "
                    "returning last result (deploy will fail)"
                )
                logger.warning("")
                return last_result
        else:
            # Not a CompletedProcess; return as-is
            return last_result

    assert last_result is not None
    return last_result
