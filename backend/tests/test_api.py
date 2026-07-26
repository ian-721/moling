from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.api import create_app
from app.models.reply import GeneratedReply
from app.providers.base import ModelRequest, ModelResponse, TokenUsage


class CapturingProvider:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            result=GeneratedReply(
                reply="先把问题缩小到今天能验证的一步。",
                mode="execution",
                safety_level="normal",
                should_ask=False,
            ),
            provider="fake",
            model="fake-test",
            usage=TokenUsage(input_tokens=100, output_tokens=20),
        )


def payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "requestId": "request-123",
        "deviceProfileId": "device-alpha",
        "assistantName": "小墨",
        "recognizedText": "今天先做哪一步",
        "recognitionSource": "mlkit",
    }
    base.update(overrides)
    return base


def test_healthz(test_settings) -> None:
    response = TestClient(create_app(settings=test_settings)).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "test",
        "provider": "fake",
    }


def test_text_path_and_assistant_name_injection(test_settings) -> None:
    provider = CapturingProvider()
    client = TestClient(create_app(settings=test_settings, provider=provider))
    response = client.post("/api/notebook/reply", json=payload())
    assert response.status_code == 200
    assert response.json()["aiReply"] == "先把问题缩小到今天能验证的一步。"
    assert response.json()["responseMode"] == "execution"
    assert "角色显示名：小墨" in provider.requests[0].user_prompt
    assert provider.requests[0].provider_user_id.startswith("moling_")


def test_empty_request_is_rejected(test_settings) -> None:
    response = TestClient(create_app(settings=test_settings)).post(
        "/api/notebook/reply",
        json=payload(recognizedText=""),
    )
    assert response.status_code == 400


def test_missing_identity_is_rejected(test_settings) -> None:
    body = payload()
    body.pop("deviceProfileId")
    body["recognizedText"] = "不能出现在错误响应里的正文"
    response = TestClient(create_app(settings=test_settings)).post(
        "/api/notebook/reply", json=body
    )
    assert response.status_code == 422
    assert "不能出现在错误响应里的正文" not in response.text


def test_missing_name_falls_back_to_moling(test_settings) -> None:
    provider = CapturingProvider()
    client = TestClient(create_app(settings=test_settings, provider=provider))
    response = client.post(
        "/api/notebook/reply", json=payload(assistantName=None)
    )
    assert response.status_code == 200
    assert "角色显示名：墨灵" in provider.requests[0].user_prompt


def test_same_name_different_users_remain_isolated(test_settings) -> None:
    provider = CapturingProvider()
    client = TestClient(create_app(settings=test_settings, provider=provider))
    first = payload(
        deviceProfileId=None,
        userId="user-one",
        assistantName="老g",
        recognizedText="我的项目一",
    )
    second = payload(
        requestId="request-456",
        deviceProfileId=None,
        userId="user-two",
        assistantName="老g",
        recognizedText="我的项目二",
    )
    assert client.post("/api/notebook/reply", json=first).status_code == 200
    assert client.post("/api/notebook/reply", json=second).status_code == 200
    assert provider.requests[0].provider_user_id != provider.requests[1].provider_user_id
    assert "我的项目二" not in provider.requests[0].user_prompt
    assert "我的项目一" not in provider.requests[1].user_prompt


def test_missing_name_never_reuses_previous_request_name(test_settings) -> None:
    provider = CapturingProvider()
    client = TestClient(create_app(settings=test_settings, provider=provider))
    assert client.post(
        "/api/notebook/reply",
        json=payload(assistantName="上一位用户的名字"),
    ).status_code == 200
    assert client.post(
        "/api/notebook/reply",
        json=payload(
            requestId="request-next",
            deviceProfileId="device-next",
            assistantName=None,
        ),
    ).status_code == 200
    assert "上一位用户的名字" not in provider.requests[1].user_prompt
    assert "角色显示名：墨灵" in provider.requests[1].user_prompt


def test_production_vision_is_closed_and_does_not_write(test_settings, tmp_path) -> None:
    marker = tmp_path / "debug_last_request.png"
    response = TestClient(create_app(settings=test_settings)).post(
        "/api/notebook/reply",
        json=payload(recognizedText=None, imageBase64="aW1hZ2U="),
    )
    assert response.status_code == 403
    assert not marker.exists()


def test_production_log_does_not_contain_user_content(
    test_settings, caplog
) -> None:
    secret_text = "这段正文绝不能进入日志"
    secret_context = "这段上下文也不能进入日志"
    provider = CapturingProvider()
    client = TestClient(create_app(settings=test_settings, provider=provider))
    with caplog.at_level(logging.INFO, logger="moling.api"):
        response = client.post(
            "/api/notebook/reply",
            json=payload(
                recognizedText=secret_text,
                recentContext=secret_context,
            ),
        )
    assert response.status_code == 200
    logs = caplog.text
    assert secret_text not in logs
    assert secret_context not in logs
    assert "先把问题缩小" not in logs
    assert "request-123" in logs
