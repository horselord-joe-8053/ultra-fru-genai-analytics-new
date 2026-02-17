"""
Teardown stats: per-component timing for kube and nonkube teardown.

Records each torn-down component with scope, identifier, and duration (seconds).
Call set_scope() before each phase so records get the correct scope label.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from tools.common.stats.table_printer import print_stats_table

# Column widths for summary table
_SCOPE_W = 20
_COMPONENT_W = 38
_IDENTIFIER_W = 50
_DURATION_W = 8


def scope_for(stack_dir: str) -> str:
    """Map stack dir to display label (nonkube|kube|shared-nondurable)."""
    if "nonkube" in stack_dir and "shared" not in stack_dir:
        return "nonkube"
    if "kube" in stack_dir and "nonkube" not in stack_dir:
        return "kube"
    if "shared" in stack_dir and "nondurable" in stack_dir:
        return "shared-nondurable"
    return stack_dir.split("/")[-1] if "/" in stack_dir else stack_dir


@dataclass
class TeardownRecord:
    """Single teardown operation record."""
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


class TeardownStats:
    """
    Collects teardown stats. Call set_scope() before each phase; use timed()
    or record() to add entries. Call print_summary() at end of run.
    """

    def __init__(self) -> None:
        self._records: list[TeardownRecord] = []
        self._current_scope: str = ""

    def set_scope(self, scope: str) -> None:
        """Set scope for subsequent records (call before each phase)."""
        self._current_scope = scope

    def record(self, component: str, identifier: str, duration_sec: float) -> None:
        """Record a completed teardown operation."""
        self._records.append(
            TeardownRecord(
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
        """Print teardown stats table at end of run (no logger prefix on table rows)."""
        print_stats_table(self._records, "Teardown stats")
