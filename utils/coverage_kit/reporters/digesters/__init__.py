"""Coverage digesters — raw artifacts → :class:`UnifiedCoverageModel`."""

from __future__ import annotations

from ..config import CoverageFinalizeResult, CoverageKitConfig
from ..model import UnifiedCoverageModel
from .backend import BackendCoverageDigester
from .base import CoverageDigester
from .playwright import PlaywrightRawDigester
from .vitest import VitestCoverageDigester

_DEFAULT_DIGESTERS: tuple[CoverageDigester, ...] = (
    BackendCoverageDigester(),
    VitestCoverageDigester(),
    PlaywrightRawDigester(),
)


def build_unified_coverage_model(
    config: CoverageKitConfig,
    *,
    finalize: CoverageFinalizeResult | None = None,
    e2e_instrumented: bool = False,
    digesters: tuple[CoverageDigester, ...] | None = None,
) -> UnifiedCoverageModel:
    """Run all digesters and attach finalize-level partial metadata when provided."""
    model = UnifiedCoverageModel(e2e_instrumented=e2e_instrumented)
    for digester in digesters or _DEFAULT_DIGESTERS:
        for surface in digester.digest(config):
            if surface is not None:
                model.surfaces.append(surface)
    if finalize is not None:
        model.partial = finalize.partial
        model.partial_reason = finalize.partial_reason or ""
        _backfill_from_finalize(model, finalize, e2e_instrumented=e2e_instrumented)
    return model


def _backfill_from_finalize(
    model: UnifiedCoverageModel,
    finalize: CoverageFinalizeResult,
    *,
    e2e_instrumented: bool,
) -> None:
    """Prefer finalize headline numbers when HTML/JSON digests are incomplete."""
    import dataclasses

    from ..model import SurfaceSnapshot

    updated: list[SurfaceSnapshot] = []
    seen: set[str] = set()
    for surface in model.surfaces:
        seen.add(surface.surface_id)
        if surface.surface_id == "backend" and finalize.backend_lines_pct is not None:
            surface = dataclasses.replace(
                surface,
                lines_pct=finalize.backend_lines_pct,
                partial=False,
            )
        elif surface.surface_id == "vitest" and finalize.vitest_lines_pct is not None:
            surface = dataclasses.replace(
                surface,
                lines_pct=finalize.vitest_lines_pct,
                partial=False,
            )
        elif surface.surface_id == "playwright_mocked":
            surface = dataclasses.replace(
                surface,
                raw_dump_count=finalize.mocked_playwright_dump_count,
            )
        elif surface.surface_id == "playwright_e2e" and e2e_instrumented:
            surface = dataclasses.replace(
                surface,
                raw_dump_count=finalize.e2e_playwright_dump_count,
            )
        updated.append(surface)

    if "backend" not in seen and finalize.backend_lines_pct is not None:
        updated.insert(
            0,
            SurfaceSnapshot(
                surface_id="backend",
                label="Backend (combined unittest + openapi)",
                lines_pct=finalize.backend_lines_pct,
                detail_href="reports/backend/index.html",
            ),
        )
    if "vitest" not in seen and finalize.vitest_lines_pct is not None:
        updated.append(
            SurfaceSnapshot(
                surface_id="vitest",
                label="Frontend Vitest",
                lines_pct=finalize.vitest_lines_pct,
                detail_href="reports/frontend/vitest-html/index.html",
            )
        )
    model.surfaces = updated


__all__ = [
    "BackendCoverageDigester",
    "CoverageDigester",
    "PlaywrightRawDigester",
    "VitestCoverageDigester",
    "build_unified_coverage_model",
]
