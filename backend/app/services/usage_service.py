from __future__ import annotations

from app.providers.base import TokenUsage

FLASH_INPUT_CNY_PER_MILLION = 1.0
FLASH_CACHE_CNY_PER_MILLION = 0.02
FLASH_OUTPUT_CNY_PER_MILLION = 2.0
PRO_INPUT_CNY_PER_MILLION = 3.0
PRO_CACHE_CNY_PER_MILLION = 0.025
PRO_OUTPUT_CNY_PER_MILLION = 6.0


def with_estimated_cost(usage: TokenUsage, *, deep_mode: bool) -> TokenUsage:
    uncached = max(usage.input_tokens - usage.cache_hit_tokens, 0)
    if deep_mode:
        input_rate, cache_rate, output_rate = (
            PRO_INPUT_CNY_PER_MILLION,
            PRO_CACHE_CNY_PER_MILLION,
            PRO_OUTPUT_CNY_PER_MILLION,
        )
    else:
        input_rate, cache_rate, output_rate = (
            FLASH_INPUT_CNY_PER_MILLION,
            FLASH_CACHE_CNY_PER_MILLION,
            FLASH_OUTPUT_CNY_PER_MILLION,
        )
    cost = (
        uncached * input_rate
        + usage.cache_hit_tokens * cache_rate
        + usage.output_tokens * output_rate
    ) / 1_000_000
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_hit_tokens=usage.cache_hit_tokens,
        estimated_cost_cny=round(cost, 8),
    )
