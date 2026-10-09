from __future__ import annotations

from typing import Protocol

from utils.llm_cost.types import PriceSnapshotRef, UsageEvent


class LlmCostRepository(Protocol):
    def save_usage_event(
        self, event: UsageEvent, snapshot: PriceSnapshotRef | None, *, commit: bool = True
    ) -> int:
        """Persist one usage event and return row id. When ``commit`` is false, only flush (same outer transaction)."""

    def get_price_snapshot(self, provider: str, model: str) -> PriceSnapshotRef | None:
        """Return active price snapshot for provider+model, if any."""

