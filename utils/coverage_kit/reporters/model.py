"""Unified in-memory coverage model (Stage 2a) for dashboard and ops summary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileCoverage:
    """Per-file headline metrics when a digester can list them."""

    path: str
    lines_pct: float | None = None


@dataclass(frozen=True)
class SurfaceSnapshot:
    """One measurable coverage surface (backend, Vitest, Playwright raw, …)."""

    surface_id: str
    label: str
    lines_pct: float | None = None
    """Primary line % (backend/Vitest) or **frontend** Istanbul % for Playwright surfaces."""
    backend_lines_pct: float | None = None
    """``apps/api`` line % when this surface exercised a real API (E2E stack)."""
    statements_pct: float | None = None
    functions_pct: float | None = None
    branches_pct: float | None = None
    file_count: int | None = None
    raw_dump_count: int | None = None
    detail_href: str | None = None
    partial: bool = False
    notes: str = ""
    top_files: tuple[FileCoverage, ...] = ()


@dataclass
class UnifiedCoverageModel:
    """All digested surfaces plus ritual-level partial flags."""

    surfaces: list[SurfaceSnapshot] = field(default_factory=list)
    partial: bool = False
    partial_reason: str = ""
    e2e_instrumented: bool = False

    def by_id(self, surface_id: str) -> SurfaceSnapshot | None:
        for surface in self.surfaces:
            if surface.surface_id == surface_id:
                return surface
        return None

    def overview_rows(self) -> list[SurfaceSnapshot]:
        """Surfaces shown in the dashboard overview table (stable order)."""
        order = (
            "backend",
            "vitest",
            "playwright_mocked",
            "playwright_e2e",
        )
        by_id = {s.surface_id: s for s in self.surfaces}
        rows: list[SurfaceSnapshot] = []
        for sid in order:
            if sid in by_id:
                rows.append(by_id[sid])
        for s in self.surfaces:
            if s.surface_id not in order:
                rows.append(s)
        return rows
