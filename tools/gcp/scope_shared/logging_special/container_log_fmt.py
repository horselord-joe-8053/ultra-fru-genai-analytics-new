"""
Cascaded gray formatting for Cloud Run Job container logs.
Used by db-setup cloud_job and any other GCP container log display.
"""

CONTAINER_LOG_GRAY = "\033[38;5;250m\033[3m"
CONTAINER_LOG_RESET = "\033[0m"
CONTAINER_LOG_INDENT = "      "  # Hierarchical indent for container lines


def format_container_log_line(line: str) -> str:
    """Format a single container log line with gray italic."""
    return f"{CONTAINER_LOG_INDENT}{CONTAINER_LOG_GRAY}{line}{CONTAINER_LOG_RESET}"


def format_container_log_header(primary_cmd: str, line_count: int) -> str:
    """Standard header for container log blocks."""
    return f'Last {line_count} line(s) from the Cloud Run container based on "{primary_cmd}"'


def format_container_log_block(lines: list[str], header: str) -> str:
    """Format a block of container lines with header. For heartbeat messages."""
    formatted = "\n".join(format_container_log_line(l) for l in lines)
    return f"  {CONTAINER_LOG_GRAY}{header}{CONTAINER_LOG_RESET}\n{formatted}"
