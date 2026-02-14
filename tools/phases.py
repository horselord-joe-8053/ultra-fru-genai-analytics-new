"""
Phase tracking for deploy and teardown.
Provides flexible, computed phase numbering and timing logs.
"""
import time
from typing import Sequence

from tools import logger


def _format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if m > 0:
        return f"{m}m{s}s"
    return f"{s}s"


class PhaseTracker:
    """
    Tracks phases for Deploy or Teardown with flexible numbering and timing.
    Usage:
        tracker = PhaseTracker("Deploy", ["Doctor", "Backend", "Shared durable", ...])
        for i, name in enumerate(tracker.phases, 1):
            tracker.start_phase(i)
            do_work()
            tracker.end_phase(i)
    """

    def __init__(self, operation: str, phases: Sequence[str]):
        self.operation = operation  # "Deploy" | "Teardown"
        self.phases = list(phases)
        self.total = len(self.phases)
        self.start_time = time.time()
        self._phase_start: float | None = None

    def start_phase(self, idx: int) -> None:
        self._phase_start = time.time()

    def end_phase(self, idx: int) -> None:
        if self._phase_start is None:
            return
        phase_secs = int(time.time() - self._phase_start)
        total_secs = int(time.time() - self.start_time)
        phase_name = self.phases[idx - 1] if 1 <= idx <= len(self.phases) else f"Phase {idx}"
        phase_dur = _format_duration(phase_secs)
        total_dur = _format_duration(total_secs)
        msg = (
            f"--- Phase {idx} of {self.total} of {self.operation} completed: {phase_name}; "
            f"Phase: {phase_dur}, Total: {total_dur} ---"
        )
        logger.info(msg)


def deploy_phases(scope: str) -> list[str]:
    """Return phase names for deploy (order matches deploy.py main loop)."""
    return [
        "Doctor checks",
        "State backend bootstrap",
        "Shared durable (VPC + Aurora + Secrets)",
        "Shared nondurable (ECR + S3)",
        "Secrets in Secrets Manager",
        "Database setup (pgvector, schema, data)",
        "Build and push images",
        "ECR image URLs",
        "Apply stack (kube/nonkube)",
        "Bootstrap (K8s/ECS)",
    ]


def teardown_phases(scope: str) -> list[str]:
    """Return phase names for teardown (order matches teardown scope)."""
    if scope == "kube":
        return ["Pre-destroy (remove CronJob/Job)", "Destroy kube stack"]
    if scope == "nonkube":
        return ["Destroy nonkube stack"]
    # scope == "all"
    return [
        "Pre-destroy (remove CronJob/Job)",
        "Destroy nonkube stack",
        "Destroy kube stack",
        "Destroy shared-nondurable",
    ]
