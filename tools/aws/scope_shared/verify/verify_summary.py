"""
Verify summary: tabular output for verify_all_deploy results.

Uses print() (no logger prefix) for clean table display with colors.
"""
from dataclasses import dataclass
from typing import Sequence

# ANSI colors (aligned with tools.cloud_shared.logging.logger)
GREEN = "\033[0;32m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"

# Column widths (compact)
_SCOPE_W = 10
_ENDPOINT_W = 12
_STATUS_W = 6
_NOTES_W = 45


@dataclass
class VerifyRow:
    """Single row in the verify summary table."""
    scope: str
    endpoint: str
    ok: bool
    notes: str = ""


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if needed."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _format_row(row: VerifyRow) -> str:
    """Format a single row; status uses color (fixed 5-char display)."""
    notes = _truncate(row.notes, _NOTES_W)
    status = f"{GREEN}  ✓  {NC}" if row.ok else f"{RED}  ✗  {NC}"
    return (
        f"{row.scope:<{_SCOPE_W}} "
        f"{row.endpoint:<{_ENDPOINT_W}} "
        f"{status} "
        f"{notes}"
    )


def print_verify_summary(
    rows: Sequence[VerifyRow],
    env: str,
    total_rec: int,
) -> None:
    """
    Print verification summary table using print() (no logger prefix).
    Uses colors for status: green ✓ for pass, red ✗ for fail.
    """
    header = (
        f"{'Scope':<{_SCOPE_W}} "
        f"{'Endpoint':<{_ENDPOINT_W}} "
        f"{'Status':<{_STATUS_W}} "
        f"{'URL / Notes':<{_NOTES_W}}"
    )
    sep = "-" * (len(header) + 10)  # +10 for ANSI codes in status column

    print()
    print(f"{BLUE}==> Full Verification (env: {env}, total_rec: {total_rec}){NC}")
    print()
    print(header)
    print(sep)
    for row in rows:
        print(_format_row(row))
    print(sep)
    print()
