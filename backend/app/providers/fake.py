from __future__ import annotations

from app.models.reply import GeneratedReply
from app.providers.base import ModelRequest, ModelResponse, TokenUsage


class FakeProvider:
    """Deterministic local provider. Production configuration rejects it."""

    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            result=GeneratedReply(
                reply="这是一条本地模拟回应。真实部署只需注入 DeepSeek Secret。",
                mode="execution",
                safety_level="normal",
                should_ask=False,
                memory_candidates=[],
            ),
            provider="fake",
            model="fake-m0a",
            usage=TokenUsage(),
        )
