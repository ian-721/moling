from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.models.reply import GeneratedReply


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_tokens: int = 0
    estimated_cost_cny: float = 0.0


@dataclass(frozen=True)
class ModelRequest:
    system_prompt: str
    user_prompt: str
    provider_user_id: str
    prompt_version: str
    deep_mode: bool = False


@dataclass(frozen=True)
class ModelResponse:
    result: GeneratedReply
    provider: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    degraded: bool = False


class ProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        provider_status: int | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.provider_status = provider_status
        self.retriable = retriable


class EmptyContentError(ProviderError):
    def __init__(self) -> None:
        super().__init__("empty_content", retriable=True)


class InvalidProviderJsonError(ProviderError):
    def __init__(self) -> None:
        super().__init__("invalid_provider_json", retriable=True)


class ModelProvider(Protocol):
    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        """Generate one validated structured notebook reply."""
