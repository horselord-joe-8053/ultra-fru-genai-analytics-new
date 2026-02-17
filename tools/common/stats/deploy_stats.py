"""
Deploy stats: per-phase timing for kube and nonkube deploy.

Records each deploy phase with scope, component, and duration (seconds).
Call set_scope() before each phase so records get the correct scope label.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from tools.common.stats.table_printer import print_stats_table

# Column widths (match teardown_stats for consistency)
_SCOPE_W = 20
_COMPONENT_W = 38
_IDENTIFIER_W = 50
_DURATION_W = 8


@dataclass
class DeployRecord:
    """Single deploy phase record."""
    scope: str
    component: str
    identifier: str
    duration_sec: float

    def __str__(self) -> str:
        return (
            f"{self.scope:<{_SCOPE_W}} "
            f"{self.component:<{_COMPONENT_W}} "
            f"{self.identifier:<{_IDENTIFIER_W}} "
            f"{self.duration_sec:>6.1f}s"
        )


class DeployStats:
    """
    Collects deploy stats. Call set_scope() before each phase; use timed()
    or record() to add entries. Call print_summary() at end of run.
    """

    def __init__(self) -> None:
        self._records: list[DeployRecord] = []
        self._current_scope: str = ""

    def set_scope(self, scope: str) -> None:
        """Set scope for subsequent records (call before each phase)."""
        self._current_scope = scope

    def record(self, component: str, identifier: str, duration_sec: float) -> None:
        """Record a completed deploy phase."""
        self._records.append(
            DeployRecord(
                scope=self._current_scope,
                component=component,
                identifier=identifier,
                duration_sec=duration_sec,
            )
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
        """Print deploy stats table at end of run (no logger prefix on table rows)."""
        print_stats_table(self._records, "Deploy stats")
