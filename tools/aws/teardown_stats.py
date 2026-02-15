"""
Teardown stats: per-component timing for kube and nonkube teardown.

Records each torn-down component with identifier and duration (seconds).
If a resource was already removed, duration is near zero.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from tools import logger


@dataclass
class TeardownRecord:
    """Single teardown operation record."""
    component: str
    identifier: str
    duration_sec: float

    def __str__(self) -> str:
        return f"{self.component:40} {self.identifier:50} {self.duration_sec:>6.1f}s"


class TeardownStats:
    """
    Collects teardown stats for kube and nonkube. Use timed() context manager
    or record() to add entries. Call print_summary() at end of run.
    """

    def __init__(self) -> None:
        self._records: list[TeardownRecord] = []

    def record(self, component: str, identifier: str, duration_sec: float) -> None:
        """Record a completed teardown operation."""
        self._records.append(
            TeardownRecord(component=component, identifier=identifier, duration_sec=duration_sec)
        )

    @contextmanager
    def timed(self, component: str, identifier: str) -> Iterator[None]:
        """Context manager: records duration on exit."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.record(component, identifier, duration)

    def print_summary(self) -> None:
        """Print teardown stats table at end of run."""
        if not self._records:
            return
        logger.step("Teardown stats:")
        header = f"{'Component':<40} {'Identifier':<50} {'Duration':>8}"
        logger.info(header)
        logger.info("-" * len(header))
        for r in self._records:
            logger.info(str(r))
        total = sum(r.duration_sec for r in self._records)
        logger.info("-" * len(header))
        logger.info(f"{'Total':<40} {'':<50} {total:>6.1f}s")
