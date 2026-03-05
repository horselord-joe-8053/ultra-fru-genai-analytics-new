"""
Phase tracking for deploy and teardown. Shared across AWS and GCP.
Provides flexible, computed phase numbering and timing logs.
"""
import time
from typing import Sequence

from tools.cloud_shared.logging import logger


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
        phase_name = self.phases[idx - 1] if 1 <= idx <= len(self.phases) else f"Phase {idx}"
        logger.phase_start(idx, self.total, phase_name)

    def end_phase(self, idx: int) -> None:
        if self._phase_start is None:
            return
        phase_secs = int(time.time() - self._phase_start)
        phase_name = self.phases[idx - 1] if 1 <= idx <= len(self.phases) else f"Phase {idx}"
        logger.phase_end(idx, self.total, phase_name, phase_secs)
