from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PriceSnapshotRef:
    provider: str
    model: str
    input_price_usd_per_1m: Decimal
    output_price_usd_per_1m: Decimal
    cached_input_price_usd_per_1m: Decimal | None = None
    last_modified_at: datetime | None = None


@dataclass(frozen=True)
class UsageEvent:
    provider: str
    model: str
    feature: str
    input_tokens: int
    output_tokens: int
    run_id: int | None = None
    item_key: str | None = None
    request_started_at: datetime | None = None
    request_finished_at: datetime | None = None

