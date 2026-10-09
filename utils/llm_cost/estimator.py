from __future__ import annotations

from decimal import Decimal

from utils.llm_cost.types import PriceSnapshotRef, UsageEvent

_ONE_M = Decimal("1000000")


def estimate_cost_usd(event: UsageEvent, snapshot: PriceSnapshotRef) -> Decimal:
    """Estimate event USD cost from raw tokens and per-1M pricing."""
    input_cost = (Decimal(event.input_tokens) / _ONE_M) * snapshot.input_price_usd_per_1m
    output_cost = (Decimal(event.output_tokens) / _ONE_M) * snapshot.output_price_usd_per_1m
    return input_cost + output_cost

