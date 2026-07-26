from __future__ import annotations

import logging
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import create_app
from app.db_models import AccessToken, ReplyRequest, UsageWindow
from app.models.reply import GeneratedReply, NotebookReplyRequest
from app.providers.base import (
    ModelRequest,
    ModelResponse,
    ProviderError,
    TokenUsage,
)
from app.services.request_service import request_fingerprint


class CapturingProvider:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.requests: list[ModelRequest] = []
        self.fail_once = fail_once

    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail_once and len(self.requests) == 1:
            raise ProviderError("provider_unavailable", retriable=True)
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


class BlockingProvider(CapturingProvider):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    async def generate_reply(self, request: ModelRequest) -> ModelResponse:
        self.entered.set()
        await asyncio.to_thread(self.release.wait, 5)
        return await super().generate_reply(request)


INSTALLATION_A = "12345678-1234-1234-1234-123456789012"
INSTALLATION_B = "22345678-1234-1234-1234-123456789012"


def register(client: TestClient, installation_id: str = INSTALLATION_A) -> str:
    response = client.post(
        "/api/auth/device/register",
        json={"installationId": installation_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "requestId": "request-123",
        "recognizedText": "今天先做哪一步",
        "recognitionSource": "mlkit",
    }
    body.update(overrides)
    return body


def test_health_and_readiness_do_not_expose_usage(test_settings) -> None:
    with TestClient(create_app(settings=test_settings)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ready"}
        assert "budget" not in client.get("/healthz").text


def test_device_registration_hashes_token_and_defaults_profile(
    test_settings,
) -> None:
    app = create_app(settings=test_settings)
    with TestClient(app) as client:
        token = register(client)
        profile = client.get("/api/profile", headers=bearer(token))
        assert profile.status_code == 200
        assert profile.json()["assistantName"] == "墨灵"
        with app.state.session_factory() as session:
            stored = session.scalar(select(AccessToken))
            assert stored is not None
            assert stored.token_hash != token
            assert len(stored.token_hash) == 64


def test_existing_installation_requires_authenticated_rotation(test_settings) -> None:
    with TestClient(create_app(settings=test_settings)) as client:
        token = register(client)
        conflict = client.post(
            "/api/auth/device/register",
            json={"installationId": INSTALLATION_A},
        )
        assert conflict.status_code == 409
        rotated = client.post(
            "/api/auth/device/register",
            headers=bearer(token),
            json={"installationId": INSTALLATION_A},
        )
        assert rotated.status_code == 200
        new_token = rotated.json()["accessToken"]
        assert new_token != token
        assert client.get("/api/profile", headers=bearer(token)).status_code == 401
        assert client.get("/api/profile", headers=bearer(new_token)).status_code == 200


def test_missing_invalid_expired_and_revoked_token_are_unauthorized(
    test_settings,
) -> None:
    app = create_app(settings=test_settings)
    with TestClient(app) as client:
        assert client.get("/api/profile").status_code == 401
        assert client.get(
            "/api/profile", headers=bearer("not-a-valid-token")
        ).status_code == 401
        token = register(client)
        with app.state.session_factory.begin() as session:
            stored = session.scalar(select(AccessToken))
            assert stored is not None
            stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert client.get("/api/profile", headers=bearer(token)).status_code == 401

        second = register(client, INSTALLATION_B)
        with app.state.session_factory.begin() as session:
            stored = session.scalar(
                select(AccessToken).where(
                    AccessToken.revoked_at.is_(None),
                    AccessToken.expires_at > datetime.now(timezone.utc),
                )
            )
            assert stored is not None
            stored.revoked_at = datetime.now(timezone.utc)
        assert client.get("/api/profile", headers=bearer(second)).status_code == 401


def test_profile_update_is_server_authoritative_and_same_names_are_isolated(
    test_settings,
) -> None:
    provider = CapturingProvider()
    with TestClient(
        create_app(settings=test_settings, provider=provider)
    ) as client:
        first = register(client, INSTALLATION_A)
        second = register(client, INSTALLATION_B)
        assert client.patch(
            "/api/profile",
            headers=bearer(first),
            json={"assistantName": "老g"},
        ).status_code == 200
        assert client.patch(
            "/api/profile",
            headers=bearer(second),
            json={"assistantName": "老g"},
        ).status_code == 200

        malicious = payload(
            userId="another-user",
            deviceProfileId=INSTALLATION_B,
            assistantName="冒充名称",
        )
        assert client.post(
            "/api/notebook/reply", headers=bearer(first), json=malicious
        ).status_code == 200
        malicious["requestId"] = "request-second"
        assert client.post(
            "/api/notebook/reply", headers=bearer(second), json=malicious
        ).status_code == 200
        assert "角色显示名：老g" in provider.requests[0].user_prompt
        assert "冒充名称" not in provider.requests[0].user_prompt
        assert (
            provider.requests[0].provider_user_id
            != provider.requests[1].provider_user_id
        )


def test_profile_rejects_blank_control_and_long_names(test_settings) -> None:
    with TestClient(create_app(settings=test_settings)) as client:
        token = register(client)
        for name in ("  ", "bad\u0001name", "这个角色名称确定已经超过十六个字了"):
            response = client.patch(
                "/api/profile",
                headers=bearer(token),
                json={"assistantName": name},
            )
            assert response.status_code == 400
        assert (
            client.get("/api/profile", headers=bearer(token)).json()[
                "assistantName"
            ]
            == "墨灵"
        )


def test_reply_requires_bearer_and_idempotent_success_replays(test_settings) -> None:
    provider = CapturingProvider()
    with TestClient(
        create_app(settings=test_settings, provider=provider)
    ) as client:
        assert client.post("/api/notebook/reply", json=payload()).status_code == 401
        token = register(client)
        first = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        replay = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert first.status_code == replay.status_code == 200
        assert first.json() == replay.json()
        assert len(provider.requests) == 1


def test_idempotency_conflict_and_different_principal_scope(test_settings) -> None:
    provider = CapturingProvider()
    with TestClient(
        create_app(settings=test_settings, provider=provider)
    ) as client:
        first = register(client, INSTALLATION_A)
        second = register(client, INSTALLATION_B)
        assert client.post(
            "/api/notebook/reply", headers=bearer(first), json=payload()
        ).status_code == 200
        assert client.post(
            "/api/notebook/reply",
            headers=bearer(first),
            json=payload(recognizedText="不同内容"),
        ).status_code == 409
        assert client.post(
            "/api/notebook/reply", headers=bearer(second), json=payload()
        ).status_code == 200
        assert len(provider.requests) == 2


def test_retryable_failure_reuses_request_id_without_charging_failure(
    test_settings,
) -> None:
    provider = CapturingProvider(fail_once=True)
    app = create_app(settings=test_settings, provider=provider)
    with TestClient(app) as client:
        token = register(client)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 502
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        assert len(provider.requests) == 2
        with app.state.session_factory() as session:
            day = session.scalar(
                select(UsageWindow).where(UsageWindow.window_kind == "day")
            )
            assert day is not None
            assert day.request_count == 1
            assert day.reserved_requests == 0


def test_expired_processing_lease_is_recovered(test_settings) -> None:
    provider = CapturingProvider()
    app = create_app(settings=test_settings, provider=provider)
    with TestClient(app) as client:
        token = register(client)
        principal_id: str
        with app.state.session_factory() as session:
            access = session.scalar(select(AccessToken))
            assert access is not None
            principal_id = access.principal_id
        request = NotebookReplyRequest.model_validate(payload())
        with app.state.session_factory.begin() as session:
            session.add(
                ReplyRequest(
                    principal_id=principal_id,
                    request_id=request.request_id,
                    request_fingerprint=request_fingerprint(request),
                    status="processing",
                    attempt_count=1,
                    lease_expires_at=datetime.now(timezone.utc)
                    - timedelta(seconds=1),
                )
            )
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        assert len(provider.requests) == 1


def test_short_rate_daily_quota_and_global_budget(test_settings) -> None:
    rate_settings = test_settings.__class__(
        **{
            **test_settings.__dict__,
            "principal_requests_per_minute": 1,
        }
    )
    with TestClient(create_app(settings=rate_settings)) as client:
        token = register(client)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        assert client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(requestId="request-two"),
        ).status_code == 429

    daily_settings = test_settings.__class__(
        **{
            **test_settings.__dict__,
            "principal_daily_request_limit": 1,
        }
    )
    with TestClient(create_app(settings=daily_settings)) as client:
        token = register(client)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        response = client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(requestId="request-two"),
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "daily_quota_exceeded"

    budget_settings = test_settings.__class__(
        **{
            **test_settings.__dict__,
            "global_monthly_budget_cny": 0.01,
        }
    )
    with TestClient(create_app(settings=budget_settings)) as client:
        token = register(client)
        response = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "global_budget_exhausted"


def test_concurrent_daily_reservation_is_atomic(test_settings) -> None:
    settings = test_settings.__class__(
        **{
            **test_settings.__dict__,
            "principal_daily_request_limit": 1,
        }
    )
    provider = BlockingProvider()
    with TestClient(create_app(settings=settings, provider=provider)) as client:
        token = register(client)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                client.post,
                "/api/notebook/reply",
                headers=bearer(token),
                json=payload(),
            )
            assert provider.entered.wait(3)
            second = client.post(
                "/api/notebook/reply",
                headers=bearer(token),
                json=payload(requestId="request-concurrent"),
            )
            provider.release.set()
            assert first.result(timeout=5).status_code == 200
        assert second.status_code == 403
        assert second.json()["detail"]["code"] == "daily_quota_exceeded"


def test_log_does_not_contain_token_body_context_or_reply(
    test_settings, caplog
) -> None:
    secret_text = "这段正文绝不能进入日志"
    secret_context = "这段上下文也不能进入日志"
    provider = CapturingProvider()
    with TestClient(
        create_app(settings=test_settings, provider=provider)
    ) as client:
        token = register(client)
        caplog.clear()
        with caplog.at_level(logging.INFO):
            response = client.post(
                "/api/notebook/reply",
                headers=bearer(token),
                json=payload(
                    recognizedText=secret_text,
                    recentContext=secret_context,
                ),
            )
        assert response.status_code == 200
        logs = caplog.text
        assert token not in logs
        assert secret_text not in logs
        assert secret_context not in logs
        assert "先把问题缩小" not in logs
        assert "request-123" in logs
