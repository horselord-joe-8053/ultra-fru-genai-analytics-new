"""Python coverage reporters (combine, digesters, dashboard, finalize).

Collectors live in ``utils.coverage_kit.collectors``; import the stable surface from
``utils.coverage_kit`` (package root re-exports).
"""

from .config import CoverageFinalizeResult, CoverageKitConfig, CoveragePhaseResult
from .digesters import build_unified_coverage_model
from .env import CoverageEnv, is_e2e_cov_enabled, load_coverage_env
from .finalize import finalize_coverage
from .model import SurfaceSnapshot, UnifiedCoverageModel

__all__ = [
    "CoverageEnv",
    "CoverageFinalizeResult",
    "CoverageKitConfig",
    "CoveragePhaseResult",
    "SurfaceSnapshot",
    "UnifiedCoverageModel",
    "build_unified_coverage_model",
    "finalize_coverage",
    "is_e2e_cov_enabled",
    "load_coverage_env",
]
