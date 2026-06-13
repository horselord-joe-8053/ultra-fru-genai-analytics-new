"""Portable coverage kit — reporters (Python) + collectors (TypeScript).

Copy ``utils/coverage_kit/`` with ``HOWTO_USE_COVERAGE_KIT.md``. Collectors stay in test
runners; reporters finalize artifacts after a ritual completes.
"""

from .reporters import (
    CoverageEnv,
    CoverageFinalizeResult,
    CoverageKitConfig,
    CoveragePhaseResult,
    SurfaceSnapshot,
    UnifiedCoverageModel,
    build_unified_coverage_model,
    finalize_coverage,
    is_e2e_cov_enabled,
    load_coverage_env,
)

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
