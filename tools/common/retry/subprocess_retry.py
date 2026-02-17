"""
Run subprocess with configurable retry on retriable errors.
Uses config/retry_config.json for patterns, max_retries, and wait_sec.
"""
import subprocess
from typing import Optional

from tools.common.logging import logger
from tools.common.retry.retry_config import RetryConfig, get_retry_config
from tools.common.retry.with_heartbeat import (
    run_with_heartbeat,
    run_with_heartbeat_stream_capture,
    sleep_with_heartbeat,
)


def run_with_retry(
    cmd: list,
    cwd: str,
    env: dict,
    description: str = "",
    config: Optional[RetryConfig] = None,
    config_path: Optional[str] = None,
    heartbeat_interval_sec: Optional[int] = None,
    stream_output: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run command with retry on configurable retriable errors.
    Non-retriable patterns fail immediately. Retriable patterns trigger wait + retry.
    If stream_output=True, streams child stdout/stderr for fine-grained progress (e.g. tofu destroy).
    """
    cfg = config or get_retry_config(config_path)

    def _run():
        if stream_output:
            return run_with_heartbeat_stream_capture(
                cmd, cwd=cwd, env=env, description=description, interval_sec=heartbeat_interval_sec
            )
        return run_with_heartbeat(
            cmd, cwd=cwd, env=env, description=description, interval_sec=heartbeat_interval_sec
        )

    result = _run()
    if result.returncode == 0:
        return result

    err_text = (result.stderr or "") + (result.stdout or "")

    # 1. Non-retriable: fail fast
    for pattern in cfg.non_retriable:
        if pattern in err_text:
            logger.error(f"Non-retriable error matched: {pattern}")
            if result.stderr:
                logger.error(result.stderr)
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )

    # 2. Retriable: find matching rule, retry
    for rule in cfg.retriable:
        if rule.pattern in err_text:
            last_result = result
            for attempt in range(rule.max_retries):
                logger.warning(
                    f"Retriable error matched: {rule.id} ({rule.pattern}). "
                    f"Waiting {rule.wait_sec}s before retry (attempt {attempt + 1}/{rule.max_retries})"
                )
                sleep_with_heartbeat(rule.wait_sec, f"Retry {rule.id}")
                retry_result = _run()
                last_result = retry_result
                if retry_result.returncode == 0:
                    return retry_result
                err_text = (retry_result.stderr or "") + (retry_result.stdout or "")
                if rule.pattern not in err_text:
                    break  # different error on retry
            if last_result.stderr:
                logger.error(last_result.stderr)
            raise subprocess.CalledProcessError(
                last_result.returncode, last_result.args, last_result.stdout, last_result.stderr
            )

    # 3. No matching rule: fail
    if result.stderr:
        logger.error(result.stderr)
    raise subprocess.CalledProcessError(
        result.returncode, result.args, result.stdout, result.stderr
    )
