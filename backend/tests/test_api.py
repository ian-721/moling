from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite

from app.api import create_app
from app.db_models import (
    AccessToken,
    DeviceInstallation,
    GlobalBudgetWindow,
    Principal,
    RegistrationWindow,
    ReplyRequest,
    UsageWindow,
)
from app.models.reply import GeneratedReply, NotebookReplyRequest
from app.providers.base import (
    ModelRequest,
    ModelResponse,
    ProviderError,
    TokenUsage,
)
from app.providers.deepseek import DeepSeekProvider
from app.services.auth_service import _registration_insert_statement
from app.services.request_service import request_fingerprint
from app.services.usage_service import UsageService, with_estimated_cost


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


def file_database_settings(test_settings, tmp_path, **overrides: object):
    values = {
        **test_settings.__dict__,
        "database_url": f"sqlite:///{(tmp_path / 'moling-test.db').as_posix()}",
        **overrides,
    }
    return test_settings.__class__(**values)


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
            row = ReplyRequest(
                    principal_id=principal_id,
                    request_id=request.request_id,
                    request_fingerprint=request_fingerprint(request),
                    status="provider_not_started",
                    attempt_count=1,
                    lease_expires_at=datetime.now(timezone.utc)
                    - timedelta(seconds=1),
                )
            session.add(row)
            session.flush()
            UsageService(test_settings).reserve(session, row)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        assert len(provider.requests) == 1


def test_provider_success_before_snapshot_failure_becomes_outcome_unknown(
    test_settings,
) -> None:
    now = [datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc)]
    provider = CapturingProvider()
    fail_commit = [True]

    def crash_before_commit() -> None:
        if fail_commit[0]:
            fail_commit[0] = False
            raise RuntimeError("simulated database commit failure")

    app = create_app(
        settings=test_settings,
        provider=provider,
        clock=lambda: now[0],
        before_success_commit=crash_before_commit,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        token = register(client)
        first = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert first.status_code == 500
        assert len(provider.requests) == 1
        now[0] += timedelta(seconds=test_settings.request_lease_seconds + 1)
        retry = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert retry.status_code == 409
        assert retry.json()["detail"]["code"] == "request_outcome_unknown"
        assert len(provider.requests) == 1
        with app.state.session_factory() as session:
            row = session.scalar(select(ReplyRequest))
            assert row is not None
            assert row.status == "outcome_unknown"
            assert row.reservation_state == "settled"


def test_reservation_settles_original_windows_across_month_boundary(
    test_settings,
) -> None:
    now = [datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)]

    class CrossingProvider(CapturingProvider):
        async def generate_reply(self, request: ModelRequest) -> ModelResponse:
            result = await super().generate_reply(request)
            now[0] = datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc)
            return result

    app = create_app(
        settings=test_settings,
        provider=CrossingProvider(),
        clock=lambda: now[0],
    )
    with TestClient(app) as client:
        token = register(client)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 200
        with app.state.session_factory() as session:
            day = session.scalar(
                select(UsageWindow).where(
                    UsageWindow.window_kind == "day",
                    UsageWindow.window_start
                    == datetime(2026, 7, 31, tzinfo=timezone.utc),
                )
            )
            month = session.scalar(
                select(UsageWindow).where(
                    UsageWindow.window_kind == "month",
                    UsageWindow.window_start
                    == datetime(2026, 7, 1, tzinfo=timezone.utc),
                )
            )
            budget = session.get(
                GlobalBudgetWindow,
                datetime(2026, 7, 1, tzinfo=timezone.utc),
            )
            assert day is not None and day.request_count == 1
            assert day.reserved_requests == 0
            assert month is not None and month.request_count == 1
            assert month.reserved_requests == 0
            assert budget is not None and budget.reserved_cost_cny == 0


def test_expired_unstarted_lease_releases_original_window_before_reacquire(
    test_settings,
) -> None:
    old_now = datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc)
    now = [datetime(2026, 8, 1, 0, 1, tzinfo=timezone.utc)]
    provider = CapturingProvider()
    app = create_app(
        settings=test_settings,
        provider=provider,
        clock=lambda: now[0],
    )
    with TestClient(app) as client:
        token = register(client)
        with app.state.session_factory() as session:
            access = session.scalar(select(AccessToken))
            assert access is not None
            principal_id = access.principal_id
        request = NotebookReplyRequest.model_validate(payload())
        with app.state.session_factory.begin() as session:
            row = ReplyRequest(
                principal_id=principal_id,
                request_id=request.request_id,
                request_fingerprint=request_fingerprint(request),
                status="provider_not_started",
                attempt_count=1,
                lease_expires_at=old_now - timedelta(seconds=1),
            )
            session.add(row)
            session.flush()
            UsageService(
                test_settings,
                clock=lambda: old_now,
            ).reserve(session, row)

        response = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert response.status_code == 200
        assert len(provider.requests) == 1
        with app.state.session_factory() as session:
            days = list(
                session.scalars(
                    select(UsageWindow)
                    .where(UsageWindow.window_kind == "day")
                    .order_by(UsageWindow.window_start)
                )
            )
            assert [(item.request_count, item.reserved_requests) for item in days] == [
                (0, 0),
                (1, 0),
            ]
            budgets = list(
                session.scalars(
                    select(GlobalBudgetWindow).order_by(
                        GlobalBudgetWindow.window_start
                    )
                )
            )
            assert len(budgets) == 2
            assert all(item.reserved_cost_cny == 0 for item in budgets)


def test_attempt_limit_failure_is_committed(test_settings) -> None:
    settings = test_settings.__class__(
        **{**test_settings.__dict__, "request_max_attempts": 1}
    )
    provider = CapturingProvider(fail_once=True)
    app = create_app(settings=settings, provider=provider)
    with TestClient(app) as client:
        token = register(client)
        assert client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        ).status_code == 502
        limited = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert limited.status_code == 409
        assert (
            limited.json()["detail"]["code"]
            == "request_attempt_limit_exceeded"
        )
        with app.state.session_factory() as session:
            row = session.scalar(select(ReplyRequest))
            assert row is not None
            assert row.status == "permanent_failed"
            assert row.error_category == "attempt_limit_exceeded"
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


def test_monthly_quota_and_provider_usage_settlement(test_settings) -> None:
    settings = test_settings.__class__(
        **{
            **test_settings.__dict__,
            "principal_monthly_request_limit": 1,
        }
    )
    app = create_app(settings=settings, provider=CapturingProvider())
    with TestClient(app) as client:
        token = register(client)
        first = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert first.status_code == 200
        second = client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(requestId="request-two"),
        )
        assert second.status_code == 403
        assert second.json()["detail"]["code"] == "monthly_quota_exceeded"

        with app.state.session_factory() as session:
            day = session.scalar(
                select(UsageWindow).where(UsageWindow.window_kind == "day")
            )
            month = session.scalar(
                select(UsageWindow).where(UsageWindow.window_kind == "month")
            )
            budget = session.scalar(select(GlobalBudgetWindow))
            assert day is not None
            assert month is not None
            assert budget is not None
            for window in (day, month):
                assert window.request_count == 1
                assert window.reserved_requests == 0
                assert window.input_tokens == 100
                assert window.output_tokens == 20
                assert window.estimated_cost_cny > 0
            assert budget.reserved_cost_cny == 0
            assert budget.settled_cost_cny == month.estimated_cost_cny


def test_mixed_model_cost_settles_request_usage_and_budget(
    test_settings,
    tmp_path,
) -> None:
    models: list[str] = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        request_body = json.loads(http_request.content)
        models.append(request_body["model"])
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "prompt_cache_hit_tokens": 60,
        }
        if len(models) == 1:
            return httpx.Response(
                503,
                json={"error": {"message": "private"}, "usage": usage},
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "reply": "先验证最小的一步。",
                                    "mode": "execution",
                                    "safety_level": "normal",
                                    "should_ask": False,
                                    "memory_candidates": [],
                                }
                            )
                        }
                    }
                ],
                "usage": usage,
            },
        )

    settings = file_database_settings(
        test_settings,
        tmp_path,
        model_provider="deepseek",
        deepseek_api_key="fake-test-key",
        retry_count=1,
    )
    provider = DeepSeekProvider(
        settings,
        transport=httpx.MockTransport(handler),
    )
    app = create_app(settings=settings, provider=provider)
    with TestClient(app) as client:
        token = register(client)
        response = client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(deepMode=True),
        )
        assert response.status_code == 200, response.text

    attempt_usage = TokenUsage(
        input_tokens=100,
        output_tokens=20,
        cache_hit_tokens=60,
    )
    pro_cost = with_estimated_cost(
        attempt_usage,
        deep_mode=True,
    ).estimated_cost_cny
    flash_cost = with_estimated_cost(
        attempt_usage,
        deep_mode=False,
    ).estimated_cost_cny
    expected_cost = Decimal(str(pro_cost + flash_cost))

    assert models == ["deepseek-v4-pro", "deepseek-v4-flash"]
    with app.state.session_factory() as session:
        request_row = session.scalar(select(ReplyRequest))
        day = session.scalar(
            select(UsageWindow).where(UsageWindow.window_kind == "day")
        )
        month = session.scalar(
            select(UsageWindow).where(UsageWindow.window_kind == "month")
        )
        budget = session.scalar(select(GlobalBudgetWindow))
        assert request_row is not None
        assert day is not None
        assert month is not None
        assert budget is not None
        for record in (request_row, day, month):
            assert record.input_tokens == 200
            assert record.output_tokens == 40
            assert record.cache_tokens == 120
            assert record.estimated_cost_cny == expected_cost
        assert budget.reserved_cost_cny == 0
        assert budget.settled_cost_cny == expected_cost


def test_provider_error_known_cost_is_not_repriced(
    test_settings,
    tmp_path,
) -> None:
    trusted_cost = 0.12345678

    class CostedFailureProvider(CapturingProvider):
        async def generate_reply(self, request: ModelRequest) -> ModelResponse:
            raise ProviderError(
                "provider_unavailable",
                retriable=False,
                usage=TokenUsage(
                    input_tokens=100,
                    output_tokens=20,
                    cache_hit_tokens=60,
                    estimated_cost_cny=trusted_cost,
                ),
            )

    app = create_app(
        settings=file_database_settings(test_settings, tmp_path),
        provider=CostedFailureProvider(),
    )
    with TestClient(app) as client:
        token = register(client)
        response = client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(deepMode=True),
        )
        assert response.status_code == 502

    expected_cost = Decimal("0.12345678")
    with app.state.session_factory() as session:
        request_row = session.scalar(select(ReplyRequest))
        day = session.scalar(
            select(UsageWindow).where(UsageWindow.window_kind == "day")
        )
        month = session.scalar(
            select(UsageWindow).where(UsageWindow.window_kind == "month")
        )
        budget = session.scalar(select(GlobalBudgetWindow))
        assert request_row is not None
        assert day is not None
        assert month is not None
        assert budget is not None
        assert request_row.estimated_cost_cny == expected_cost
        assert day.estimated_cost_cny == expected_cost
        assert month.estimated_cost_cny == expected_cost
        assert budget.settled_cost_cny == expected_cost


def test_registration_window_atomic_insert_contracts() -> None:
    now = datetime(2026, 7, 26, 12, 34, 56, tzinfo=timezone.utc)
    window_start = now.replace(second=0, microsecond=0)
    postgres_sql = str(
        _registration_insert_statement(
            "postgresql",
            window_start=window_start,
            now=now,
        ).compile(dialect=postgresql.dialect())
    ).upper()
    sqlite_sql = str(
        _registration_insert_statement(
            "sqlite",
            window_start=window_start,
            now=now,
        ).compile(dialect=sqlite.dialect())
    ).upper()
    for statement in (postgres_sql, sqlite_sql):
        assert "INSERT INTO REGISTRATION_WINDOWS" in statement
        assert "ON CONFLICT" in statement
        assert "DO NOTHING" in statement


def test_concurrent_distinct_registrations_share_atomic_window(
    test_settings,
    tmp_path,
) -> None:
    settings = file_database_settings(
        test_settings,
        tmp_path,
        registration_requests_per_minute=8,
    )
    now = datetime(2026, 7, 26, 12, 34, 56, tzinfo=timezone.utc)
    app = create_app(settings=settings, clock=lambda: now)
    installation_ids = [
        f"{index:08d}-1234-1234-1234-{index:012d}"
        for index in range(1, 7)
    ]
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=6) as executor:
            responses = list(
                executor.map(
                    lambda installation_id: client.post(
                        "/api/auth/device/register",
                        json={"installationId": installation_id},
                    ),
                    installation_ids,
                )
            )

    assert [response.status_code for response in responses] == [200] * 6
    with app.state.session_factory() as session:
        window = session.get(
            RegistrationWindow,
            now.replace(second=0, microsecond=0),
        )
        assert window is not None
        assert window.request_count == 6
        assert len(list(session.scalars(select(Principal)))) == 6
        assert len(list(session.scalars(select(DeviceInstallation)))) == 6


def test_concurrent_registration_limit_is_stable(
    test_settings,
    tmp_path,
) -> None:
    settings = file_database_settings(
        test_settings,
        tmp_path,
        registration_requests_per_minute=3,
    )
    now = datetime(2026, 7, 26, 12, 34, 56, tzinfo=timezone.utc)
    app = create_app(settings=settings, clock=lambda: now)
    installation_ids = [
        f"{index:08d}-2234-2234-2234-{index:012d}"
        for index in range(1, 6)
    ]
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=5) as executor:
            responses = list(
                executor.map(
                    lambda installation_id: client.post(
                        "/api/auth/device/register",
                        json={"installationId": installation_id},
                    ),
                    installation_ids,
                )
            )

    status_codes = [response.status_code for response in responses]
    assert status_codes.count(200) == 3
    assert status_codes.count(429) == 2
    assert all(
        response.json()["detail"]["code"] == "registration_rate_limited"
        for response in responses
        if response.status_code == 429
    )
    with app.state.session_factory() as session:
        window = session.get(
            RegistrationWindow,
            now.replace(second=0, microsecond=0),
        )
        assert window is not None
        assert window.request_count == 3


def test_concurrent_same_installation_has_one_safe_registration(
    test_settings,
    tmp_path,
) -> None:
    settings = file_database_settings(test_settings, tmp_path)
    now = datetime(2026, 7, 26, 12, 34, 56, tzinfo=timezone.utc)
    app = create_app(settings=settings, clock=lambda: now)
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda _: client.post(
                        "/api/auth/device/register",
                        json={"installationId": INSTALLATION_A},
                    ),
                    range(2),
                )
            )

    status_codes = sorted(response.status_code for response in responses)
    assert status_codes == [200, 409]
    conflict = next(
        response for response in responses if response.status_code == 409
    )
    assert (
        conflict.json()["detail"]["code"]
        == "installation_already_registered"
    )
    with app.state.session_factory() as session:
        assert len(list(session.scalars(select(Principal)))) == 1
        assert len(list(session.scalars(select(DeviceInstallation)))) == 1
        assert len(list(session.scalars(select(AccessToken)))) == 1


def test_concurrent_same_request_id_uses_one_provider_call_and_one_charge(
    test_settings,
) -> None:
    provider = BlockingProvider()
    app = create_app(settings=test_settings, provider=provider)
    with TestClient(app) as client:
        token = register(client)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                client.post,
                "/api/notebook/reply",
                headers=bearer(token),
                json=payload(),
            )
            assert provider.entered.wait(3)
            duplicate = client.post(
                "/api/notebook/reply",
                headers=bearer(token),
                json=payload(),
            )
            provider.release.set()
            assert first.result(timeout=5).status_code == 200

        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "request_in_progress"
        assert len(provider.requests) == 1
        replay = client.post(
            "/api/notebook/reply", headers=bearer(token), json=payload()
        )
        assert replay.status_code == 200
        assert len(provider.requests) == 1
        with app.state.session_factory() as session:
            day = session.scalar(
                select(UsageWindow).where(UsageWindow.window_kind == "day")
            )
            assert day is not None
            assert day.request_count == 1
            assert day.reserved_requests == 0


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
        token_hash = hmac.new(
            test_settings.token_hash_pepper.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert token not in logs
        assert f"Bearer {token}" not in logs
        assert "Authorization" not in logs
        assert token_hash not in logs
        assert secret_text not in logs
        assert secret_context not in logs
        assert "先把问题缩小" not in logs
        assert "request-123" in logs


def test_request_id_rejects_log_injection_characters(test_settings) -> None:
    with TestClient(create_app(settings=test_settings)) as client:
        token = register(client)
        response = client.post(
            "/api/notebook/reply",
            headers=bearer(token),
            json=payload(requestId='request-ok\\n"forged":true'),
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_request_schema"
