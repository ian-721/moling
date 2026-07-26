from __future__ import annotations

import asyncio
import json

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.models.reply import GeneratedReply
from app.providers.base import (
    EmptyContentError,
    InvalidProviderJsonError,
    ModelRequest,
    ModelResponse,
    ProviderError,
    TokenUsage,
)

RETRIABLE_STATUSES = {429, 500, 503}
KNOWN_STATUSES = {400, 401, 402, 422, 429, 500, 503}
JSON_REPAIR_HINT = (
    "\n\n上一次输出为空或格式无效。只返回最小合法 json，"
    "必须包含 reply、mode、safety_level、should_ask。"
)


class DeepSeekProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeekProvider")
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url,
            timeout=settings.timeout_seconds,
            transport=transport,
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        attempts = self.settings.retry_count + 1
        last_error: ProviderError | None = None
        use_flash_fallback = False
        json_repair_retry = False
        for attempt in range(attempts):
            try:
                response = await self._generate_once(
                    request,
                    force_flash=use_flash_fallback,
                    retry_hint=json_repair_retry,
                )
                if use_flash_fallback:
                    return ModelResponse(
                        result=response.result,
                        provider=response.provider,
                        model=response.model,
                        usage=response.usage,
                        degraded=True,
                    )
                return response
            except ProviderError as error:
                last_error = error
                if not error.retriable or attempt == attempts - 1:
                    raise
                json_repair_retry = isinstance(
                    error,
                    (EmptyContentError, InvalidProviderJsonError),
                )
                use_flash_fallback = (
                    request.deep_mode
                    and error.provider_status in {429, 503}
                )
                await asyncio.sleep(0.05 * (attempt + 1))
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                last_error = ProviderError("provider_network_error", retriable=True)
                if attempt == attempts - 1:
                    raise last_error from error
                json_repair_retry = False
                use_flash_fallback = False
                await asyncio.sleep(0.05 * (attempt + 1))
        raise last_error or ProviderError("provider_unknown_error")

    async def _generate_once(
        self,
        request: ModelRequest,
        *,
        force_flash: bool = False,
        retry_hint: bool = False,
    ) -> ModelResponse:
        model = (
            self.settings.deepseek_pro_model
            if request.deep_mode and not force_flash
            else self.settings.deepseek_flash_model
        )
        user_prompt = request.user_prompt
        if retry_hint:
            user_prompt += JSON_REPAIR_HINT
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": (
                self.settings.deep_max_tokens
                if request.deep_mode and not force_flash
                else self.settings.default_max_tokens
            ),
            "thinking": {
                "type": (
                    "enabled"
                    if request.deep_mode and not force_flash
                    else "disabled"
                )
            },
            "user_id": request.provider_user_id,
            "stream": False,
        }
        response = await self._client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            status = response.status_code
            code = (
                f"provider_http_{status}"
                if status in KNOWN_STATUSES
                else "provider_http_error"
            )
            raise ProviderError(
                code,
                provider_status=status,
                retriable=status in RETRIABLE_STATUSES,
            )

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise InvalidProviderJsonError() from error
        if not isinstance(content, str) or not content.strip():
            raise EmptyContentError()

        try:
            generated = GeneratedReply.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as error:
            raise InvalidProviderJsonError() from error

        usage_data = body.get("usage") or {}
        cache_tokens = int(
            usage_data.get("prompt_cache_hit_tokens")
            or (usage_data.get("prompt_tokens_details") or {}).get(
                "cached_tokens", 0
            )
            or 0
        )
        usage = TokenUsage(
            input_tokens=int(usage_data.get("prompt_tokens") or 0),
            output_tokens=int(usage_data.get("completion_tokens") or 0),
            cache_hit_tokens=cache_tokens,
        )
        return ModelResponse(
            result=generated,
            provider="deepseek",
            model=model,
            usage=usage,
        )

    async def close(self) -> None:
        await self._client.aclose()
