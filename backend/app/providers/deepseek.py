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
    ProviderOutcomeUnknownError,
    TokenUsage,
)

RETRIABLE_STATUSES = {429, 500, 503}
KNOWN_STATUSES = {400, 401, 402, 422, 429, 500, 503}
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
        accumulated_usage = TokenUsage()
        for attempt in range(attempts):
            try:
                response = await self._generate_once(
                    request,
                    force_flash=use_flash_fallback,
                )
                usage = _add_usage(accumulated_usage, response.usage)
                response = ModelResponse(
                    result=response.result,
                    provider=response.provider,
                    model=response.model,
                    usage=usage,
                    degraded=response.degraded,
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
                accumulated_usage = _add_usage(accumulated_usage, error.usage)
                if not error.retriable or attempt == attempts - 1:
                    error.usage = accumulated_usage
                    raise
                use_flash_fallback = (
                    request.deep_mode
                    and error.provider_status in {429, 503}
                )
                await asyncio.sleep(0.05 * (attempt + 1))
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                last_error = ProviderError("provider_network_error", retriable=True)
                if attempt == attempts - 1:
                    raise last_error from error
                use_flash_fallback = False
                await asyncio.sleep(0.05 * (attempt + 1))
            except (
                httpx.ReadTimeout,
                httpx.ReadError,
                httpx.WriteTimeout,
                httpx.WriteError,
                httpx.RemoteProtocolError,
            ) as error:
                raise ProviderOutcomeUnknownError() from error
            except httpx.RequestError as error:
                raise ProviderOutcomeUnknownError() from error
        raise last_error or ProviderError("provider_unknown_error")

    async def _generate_once(
        self,
        request: ModelRequest,
        *,
        force_flash: bool = False,
    ) -> ModelResponse:
        model = (
            self.settings.deepseek_pro_model
            if request.deep_mode and not force_flash
            else self.settings.deepseek_flash_model
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
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
        body = _safe_body(response)
        usage = _usage_from_body(body)
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
                usage=usage,
            )

        try:
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise InvalidProviderJsonError(usage) from error
        if not isinstance(content, str) or not content.strip():
            raise EmptyContentError(usage)

        try:
            generated = GeneratedReply.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as error:
            raise InvalidProviderJsonError(usage) from error
        return ModelResponse(
            result=generated,
            provider="deepseek",
            model=model,
            usage=usage,
        )

    async def close(self) -> None:
        await self._client.aclose()


def _safe_body(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _usage_from_body(body: dict) -> TokenUsage:
    usage_data = body.get("usage") or {}
    if not isinstance(usage_data, dict):
        return TokenUsage()
    details = usage_data.get("prompt_tokens_details") or {}
    cache_tokens = int(
        usage_data.get("prompt_cache_hit_tokens")
        or (details.get("cached_tokens", 0) if isinstance(details, dict) else 0)
        or 0
    )
    return TokenUsage(
        input_tokens=int(usage_data.get("prompt_tokens") or 0),
        output_tokens=int(usage_data.get("completion_tokens") or 0),
        cache_hit_tokens=cache_tokens,
    )


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        cache_hit_tokens=left.cache_hit_tokens + right.cache_hit_tokens,
        estimated_cost_cny=(
            left.estimated_cost_cny + right.estimated_cost_cny
        ),
    )
