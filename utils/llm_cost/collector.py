from __future__ import annotations

from typing import Any

from utils.llm_cost.types import UsageEvent


def usage_event_from_openai_usage(
    *,
    provider: str,
    model: str,
    feature: str,
    usage_payload: dict[str, Any],
    run_id: int | None = None,
    item_key: str | None = None,
) -> UsageEvent:
    """Normalize OpenAI-like usage payload into UsageEvent.

    Supports payloads with keys like:
      - input_tokens / output_tokens
      - prompt_tokens / completion_tokens
    """
    input_tokens = int(usage_payload.get("input_tokens", usage_payload.get("prompt_tokens", 0)) or 0)
    output_tokens = int(usage_payload.get("output_tokens", usage_payload.get("completion_tokens", 0)) or 0)
    return UsageEvent(
        provider=provider,
        model=model,
        feature=feature,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        run_id=run_id,
        item_key=item_key,
    )

