"""Colored CLI logging (timestamps, phases, heartbeats) for this repo.

``from utils.neat_logger import logger`` is the shared **ApiNeatLogger** (``logs/api.log``).
Ops roles: ``NeatLoggerFactory.ops_run_tests`` / ``ops_run_all`` — see HOWTO §4.3.
"""

from . import neat_logger as logger
from .neat_logger_instance import (
    ApiNeatLogger,
    NeatLogger,
    NeatLoggerConfig,
    NeatLoggerFactory,
    OpsRunAllLogger,
    OpsRunTestsLogger,
)

__all__ = [
    "logger",
    "NeatLogger",
    "NeatLoggerConfig",
    "NeatLoggerFactory",
    "ApiNeatLogger",
    "OpsRunTestsLogger",
    "OpsRunAllLogger",
]
