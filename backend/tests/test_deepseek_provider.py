from __future__ import annotations

import json

import httpx
import pytest
from pytest import approx

from app.config import Settings
from app.providers.base import (
    EmptyContentError,
    InvalidProviderJsonError,
    ModelRequest,
    ProviderError,
    ProviderOutcomeUnknownError,
)
from app.providers.deepseek import DeepSeekProvider
from app.services.usage_service import with_estimated_cost


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


def valid_content(reply: str = "回应") -> str:
    return json.dumps(
        {
            "reply": reply,
            "mode": "judgment",
            "safety_level": "normal",
            "should_ask": False,
            "memory_candidates": [],
        }
    )


def user_prompt(payload: dict) -> str:
    return payload["messages"][1]["content"]


@pytest.mark.asyncio
async def test_normal_json_uses_flash_and_deepseek_user_id() -> None:
    seen: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(http_request.content))
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request())
    assert response.model == "deepseek-v4-flash"
    assert response.result.reply == "回应"
    assert response.usage.cache_hit_tokens == 60
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["thinking"] == {"type": "disabled"}
    assert seen[0]["user_id"] == "moling_abcdef"
    await provider.close()


@pytest.mark.asyncio
async def test_payload_does_not_send_legacy_user_field() -> None:
    seen: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(http_request.content))
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    await provider.generate_reply(request())
    assert "user" not in seen[0]
    assert seen[0]["user_id"] == "moling_abcdef"
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
async def test_empty_content_does_not_issue_a_second_billable_call() -> None:
    calls = 0
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        bodies.append(json.loads(http_request.content))
        return httpx.Response(200, json=success_body(""))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(EmptyContentError):
        await provider.generate_reply(request())
    assert calls == 1
    await provider.close()


@pytest.mark.asyncio
async def test_invalid_json_does_not_issue_a_second_billable_call() -> None:
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
    assert calls == 1
    await provider.close()


async def assert_http_retry_does_not_add_repair_hint(status: int) -> None:
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(http_request.content))
        if len(bodies) == 1:
            return httpx.Response(status, json={"error": {"message": "private"}})
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request())
    assert response.result.reply == "回应"
    assert len(bodies) == 2
    await provider.close()


@pytest.mark.asyncio
async def test_429_retry_does_not_add_repair_hint() -> None:
    await assert_http_retry_does_not_add_repair_hint(429)


@pytest.mark.asyncio
async def test_500_retry_does_not_add_repair_hint() -> None:
    await assert_http_retry_does_not_add_repair_hint(500)


@pytest.mark.asyncio
async def test_503_retry_does_not_add_repair_hint() -> None:
    await assert_http_retry_does_not_add_repair_hint(503)


@pytest.mark.asyncio
async def test_known_usage_is_accumulated_across_controlled_http_retry() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                500,
                json={
                    "error": {"message": "private"},
                    "usage": success_body(valid_content())["usage"],
                },
            )
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request())
    assert response.usage.input_tokens == 200
    assert response.usage.output_tokens == 40
    assert response.usage.cache_hit_tokens == 120
    expected = with_estimated_cost(
        response.usage.__class__(
            input_tokens=200,
            output_tokens=40,
            cache_hit_tokens=120,
        ),
        deep_mode=False,
    )
    assert response.usage.estimated_cost_cny == approx(
        expected.estimated_cost_cny
    )
    await provider.close()


@pytest.mark.asyncio
async def test_network_retry_does_not_add_repair_hint() -> None:
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(http_request.content))
        if len(bodies) == 1:
            raise httpx.ConnectError("network unavailable", request=http_request)
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request())
    assert response.result.reply == "回应"
    assert len(bodies) == 2
    await provider.close()


@pytest.mark.asyncio
async def test_read_timeout_is_ambiguous_and_is_not_retried() -> None:
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(http_request.content))
        if len(bodies) == 1:
            raise httpx.ReadTimeout("provider timeout", request=http_request)
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderOutcomeUnknownError):
        await provider.generate_reply(request())
    assert len(bodies) == 1
    await provider.close()


@pytest.mark.asyncio
async def test_pro_503_flash_fallback_does_not_add_repair_hint() -> None:
    models: list[str] = []
    bodies: list[dict] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        bodies.append(body)
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


@pytest.mark.asyncio
async def test_pro_usage_plus_flash_usage_keeps_per_attempt_cost() -> None:
    models: list[str] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        models.append(body["model"])
        if len(models) == 1:
            return httpx.Response(
                503,
                json={
                    "error": {"message": "private"},
                    "usage": success_body(valid_content())["usage"],
                },
            )
        return httpx.Response(200, json=success_body(valid_content()))

    provider = DeepSeekProvider(
        settings(), transport=httpx.MockTransport(handler)
    )
    response = await provider.generate_reply(request(deep_mode=True))
    pro_attempt = with_estimated_cost(
        response.usage.__class__(
            input_tokens=100,
            output_tokens=20,
            cache_hit_tokens=60,
        ),
        deep_mode=True,
    )
    flash_attempt = with_estimated_cost(
        response.usage.__class__(
            input_tokens=100,
            output_tokens=20,
            cache_hit_tokens=60,
        ),
        deep_mode=False,
    )
    all_flash = with_estimated_cost(
        response.usage.__class__(
            input_tokens=200,
            output_tokens=40,
            cache_hit_tokens=120,
        ),
        deep_mode=False,
    )
    all_pro = with_estimated_cost(
        response.usage.__class__(
            input_tokens=200,
            output_tokens=40,
            cache_hit_tokens=120,
        ),
        deep_mode=True,
    )

    assert models == ["deepseek-v4-pro", "deepseek-v4-flash"]
    assert response.model == "deepseek-v4-flash"
    assert response.degraded is True
    assert response.usage.input_tokens == 200
    assert response.usage.output_tokens == 40
    assert response.usage.cache_hit_tokens == 120
    assert response.usage.estimated_cost_cny == approx(
        pro_attempt.estimated_cost_cny
        + flash_attempt.estimated_cost_cny
    )
    assert response.usage.estimated_cost_cny != approx(
        all_flash.estimated_cost_cny
    )
    assert response.usage.estimated_cost_cny != approx(
        all_pro.estimated_cost_cny
    )
    await provider.close()
