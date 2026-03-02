"""GCP-specific logging: container log formatting and Cloud Run Job log fetching."""

from .container_log_fmt import (
    CONTAINER_LOG_GRAY,
    CONTAINER_LOG_INDENT,
    CONTAINER_LOG_RESET,
    format_container_log_block,
    format_container_log_header,
    format_container_log_line,
)
from .cloud_run_logs import (
    fetch_job_logs,
    filter_container_lines_with_timestamps,
    filter_new_container_log_lines,
)

__all__ = [
    "CONTAINER_LOG_GRAY",
    "CONTAINER_LOG_INDENT",
    "CONTAINER_LOG_RESET",
    "format_container_log_block",
    "format_container_log_header",
    "format_container_log_line",
    "fetch_job_logs",
    "filter_container_lines_with_timestamps",
    "filter_new_container_log_lines",
]
