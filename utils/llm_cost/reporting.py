from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProviderSummary:
    provider: str
    model: str
    feature: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal

