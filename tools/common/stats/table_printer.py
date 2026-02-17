"""
Stats table printer: print Scope/Component/Identifier/Duration tables without logger prefix.

Uses print() for clean table display with colors. Shared by DeployStats and TeardownStats.
"""
from typing import Protocol

# ANSI colors (aligned with tools.common.logging.logger)
BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
NC = "\033[0m"

# Column widths (compact; scope fits "shared-nondurable")
_SCOPE_W = 18
_COMPONENT_W = 16
_IDENTIFIER_W = 32
_DURATION_W = 8


class StatsRecord(Protocol):
    """Protocol for records with scope, component, identifier, duration_sec."""
    scope: str
    component: str
    identifier: str
    duration_sec: float


def print_stats_table(records: list[StatsRecord], title: str) -> None:
    """
    Print stats table using print() (no logger prefix).
    Uses colors: blue for title, green for total row.
    """
    if not records:
        return

    header = (
        f"{'Scope':<{_SCOPE_W}} "
        f"{'Component':<{_COMPONENT_W}} "
        f"{'Identifier':<{_IDENTIFIER_W}} "
        f"{'Duration':>8}"
    )
    sep = "-" * len(header)
    total = sum(r.duration_sec for r in records)

    print()
    print(f"{BLUE}==> {title}{NC}")
    print()
    print(header)
    print(sep)
    for r in records:
        print(
            f"{r.scope:<{_SCOPE_W}} "
            f"{r.component:<{_COMPONENT_W}} "
            f"{r.identifier:<{_IDENTIFIER_W}} "
            f"{r.duration_sec:>6.1f}s"
        )
    print(sep)
    print(f"{GREEN}{'Total':<{_SCOPE_W}} {'':<{_COMPONENT_W}} {'':<{_IDENTIFIER_W}} {total:>6.1f}s{NC}")
    print()
