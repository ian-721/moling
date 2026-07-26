from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.providers.base import (
    EmptyContentError,
    InvalidProviderJsonError,
    ModelRequest,
    ProviderError,
)
from app.providers.deepseek import DeepSeekProvider


def settings(**overrides: object) -> Settings:
    values = {
        "environment": "test",
        "model_provider": "deepseek",
        "deepseek_api_key": "fake-test-key",
        "provider_user_id_salt": "test-salt",
        "retry_count": 1,
    }
    values.update(overrides)
    return Settings(**values)


def request(*, deep_mode: bool = False) -> ModelRequest:
    return ModelRequest(
        system_prompt="json system",
        user_prompt="user content",
        provider_user_id="moling_abcdef",
        prompt_version="persona-v1",
        deep_mode=deep_mode,
    )


def success_body(content: str | None) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "prompt_cache_hit_tokens": 60,
        },
    }


@pytest.mark.asyncio
async def test_normal_json_uses_flash_and_json_mode() -> None:
    seen: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(http_request.content))
        content = json.dumps(
            {
                "reply": "回应",
                "mode": "judgment",
                "safety_level": "normal",
                "should_ask": False,
                "memory_candidates": [],
            }
        )
        return httpx.Response(200, json=success_body(content))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request())
    assert response.model == "deepseek-v4-flash"
    assert response.result.reply == "回应"
    assert response.usage.cache_hit_tokens == 60
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["thinking"] == {"type": "disabled"}
    assert seen[0]["user"] == "moling_abcdef"
    await provider.close()


@pytest.mark.asyncio
async def test_pro_model_is_reserved() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "reply": "深度回应",
                "mode": "decision",
                "safety_level": "normal",
                "should_ask": False,
            }
        )
        return httpx.Response(200, json=success_body(content))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request(deep_mode=True))
    assert response.model == "deepseek-v4-pro"
    await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 402, 422, 429, 500, 503])
async def test_status_mapping_and_retry_count(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": {"message": "private"}})

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError) as caught:
        await provider.generate_reply(request())
    assert caught.value.code == f"provider_http_{status}"
    assert calls == (2 if status in {429, 500, 503} else 1)
    await provider.close()


@pytest.mark.asyncio
async def test_empty_content_retries_once() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=success_body(""))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(EmptyContentError):
        await provider.generate_reply(request())
    assert calls == 2
    await provider.close()


@pytest.mark.asyncio
async def test_invalid_json_retries_once() -> None:
    calls = 0
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        bodies.append(json.loads(http_request.content))
        return httpx.Response(200, json=success_body("not-json"))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(InvalidProviderJsonError):
        await provider.generate_reply(request())
    assert calls == 2
    assert "上一次输出为空或格式无效" in bodies[1]["messages"][1]["content"]
    await provider.close()


@pytest.mark.asyncio
async def test_pro_503_degrades_to_flash_once() -> None:
    models: list[str] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        models.append(body["model"])
        if len(models) == 1:
            return httpx.Response(503, json={"error": {"message": "private"}})
        content = json.dumps(
            {
                "reply": "降级回应",
                "mode": "decision",
                "safety_level": "normal",
                "should_ask": False,
            }
        )
        return httpx.Response(200, json=success_body(content))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request(deep_mode=True))
    assert models == ["deepseek-v4-pro", "deepseek-v4-flash"]
    assert response.model == "deepseek-v4-flash"
    assert response.degraded is True
    await provider.close()
