from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.db_models import AssistantProfile, Base, Principal
from app.models.auth import (
    DeviceRegistrationRequest,
    DeviceRegistrationResponse,
    ProfilePatchRequest,
    ProfileResponse,
    UsageResponse,
)
from app.models.reply import NotebookReplyRequest, NotebookReplyResponse
from app.providers.base import ModelProvider, ProviderError
from app.providers.deepseek import DeepSeekProvider
from app.providers.fake import FakeProvider
from app.services.auth_service import (
    AuthenticationError,
    AuthService,
    RegistrationError,
)
from app.services.identity_service import (
    IdentityScope,
    provider_user_id,
    validate_assistant_name,
)
from app.services.reply_service import ReplyService
from app.services.request_service import RequestService, RequestStateError
from app.services.usage_service import UsageGateError, UsageService

logger = logging.getLogger("moling.api")


def _provider_for(settings: Settings) -> ModelProvider:
    if settings.model_provider == "deepseek":
        return DeepSeekProvider(settings)
    return FakeProvider()


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _safe_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def create_app(
    *,
    settings: Settings | None = None,
    provider: ModelProvider | None = None,
    engine: Engine | None = None,
    initialize_schema: bool | None = None,
    clock: Callable[[], datetime] | None = None,
    before_success_commit: Callable[[], None] | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_provider = provider or _provider_for(active_settings)
    active_engine = engine or create_database_engine(active_settings)
    session_factory = create_session_factory(active_engine)
    auth_service = AuthService(
        active_settings,
        session_factory,
        clock=clock,
    )
    reply_service = ReplyService(active_settings, active_provider)
    request_service = RequestService(
        active_settings,
        session_factory,
        reply_service,
        clock=clock,
        before_success_commit=before_success_commit,
    )
    usage_service = UsageService(active_settings, clock=clock)
    should_initialize = (
        not active_settings.is_production
        if initialize_schema is None
        else initialize_schema
    )

    logging.basicConfig(
        level=getattr(logging, active_settings.log_level.upper(), logging.INFO),
        format=(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","event":"%(message)s"}'
        ),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if should_initialize:
            Base.metadata.create_all(active_engine)
        yield
        close = getattr(active_provider, "close", None)
        if close is not None:
            await close()
        active_engine.dispose()

    app = FastAPI(
        title="Moling API",
        version="0.8.0-m0b",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.engine = active_engine
    app.state.session_factory = session_factory

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_request_schema",
                    "message": "请求字段无效",
                }
            },
        )

    def authenticated_principal(
        authorization: str | None = Header(default=None),
    ) -> Principal:
        token = _bearer_token(authorization)
        if token is None:
            raise _safe_error(401, "missing_access_token", "需要有效的访问令牌")
        try:
            return auth_service.authenticate(token)
        except AuthenticationError as error:
            raise _safe_error(401, str(error), "访问令牌无效或已过期") from None

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        try:
            with session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            raise _safe_error(503, "database_unavailable", "服务尚未就绪") from None
        return {"status": "ready"}

    @app.post(
        "/api/auth/device/register",
        response_model=DeviceRegistrationResponse,
    )
    async def register_device(
        request: DeviceRegistrationRequest,
        authorization: str | None = Header(default=None),
    ) -> DeviceRegistrationResponse:
        rotation_principal_id: str | None = None
        if authorization is not None:
            token = _bearer_token(authorization)
            if token is None:
                raise _safe_error(
                    401, "invalid_access_token", "访问令牌无效或已过期"
                )
            try:
                rotation_principal_id = auth_service.authenticate(token).id
            except AuthenticationError:
                raise _safe_error(
                    401, "invalid_access_token", "访问令牌无效或已过期"
                ) from None
        try:
            issued = auth_service.register_device(
                request.installation_id,
                rotation_principal_id=rotation_principal_id,
            )
        except RegistrationError as error:
            messages = {
                "registration_rate_limited": "设备注册过于频繁，请稍后再试",
                "installation_already_registered": "该安装已注册，需使用现有会话轮换令牌",
                "registration_disabled": "新设备注册暂时关闭",
                "registration_capacity_reached": "设备注册容量已达到保护上限",
            }
            raise _safe_error(
                error.status_code,
                error.code,
                messages.get(error.code, "设备注册失败"),
            ) from None
        logger.info(
            "device_registered principal=%s",
            provider_user_id(
                IdentityScope("device", issued.principal.id),
                active_settings.provider_user_id_salt,
            ),
        )
        return DeviceRegistrationResponse(
            accessToken=issued.raw_token,
            expiresAt=issued.expires_at,
            profile=ProfileResponse(
                assistantName=issued.profile.assistant_name,
                updatedAt=issued.profile.updated_at,
            ),
        )

    @app.get("/api/profile", response_model=ProfileResponse)
    async def get_profile(
        principal: Principal = Depends(authenticated_principal),
    ) -> ProfileResponse:
        with session_factory() as session:
            profile = session.get(AssistantProfile, principal.id)
            if profile is None:
                raise _safe_error(404, "profile_not_found", "角色配置不存在")
            return ProfileResponse(
                assistantName=profile.assistant_name,
                updatedAt=profile.updated_at,
            )

    @app.patch("/api/profile", response_model=ProfileResponse)
    async def patch_profile(
        request: ProfilePatchRequest,
        principal: Principal = Depends(authenticated_principal),
    ) -> ProfileResponse:
        try:
            name = validate_assistant_name(request.assistant_name)
        except ValueError as error:
            raise _safe_error(400, "invalid_assistant_name", str(error)) from None
        with session_factory.begin() as session:
            profile = session.get(
                AssistantProfile, principal.id, with_for_update=True
            )
            if profile is None:
                raise _safe_error(404, "profile_not_found", "角色配置不存在")
            profile.assistant_name = name
            session.flush()
            return ProfileResponse(
                assistantName=profile.assistant_name,
                updatedAt=profile.updated_at,
            )

    @app.get("/api/usage", response_model=UsageResponse)
    async def get_usage(
        principal: Principal = Depends(authenticated_principal),
    ) -> UsageResponse:
        with session_factory.begin() as session:
            snapshot = usage_service.snapshot(session, principal.id)
        return UsageResponse(
            dailyUsed=snapshot.daily_used,
            dailyLimit=active_settings.principal_daily_request_limit,
            monthlyUsed=snapshot.monthly_used,
            monthlyLimit=active_settings.principal_monthly_request_limit,
        )

    @app.post("/api/notebook/reply", response_model=NotebookReplyResponse)
    async def notebook_reply(
        request: NotebookReplyRequest,
        principal: Principal = Depends(authenticated_principal),
    ) -> NotebookReplyResponse:
        started = time.perf_counter()
        if request.image_base64:
            if not active_settings.vision_fallback_enabled:
                raise _safe_error(403, "vision_disabled", "Vision fallback 已关闭")
            raise _safe_error(
                501,
                "vision_not_configured",
                "Vision fallback 未配置生产 Provider",
            )
        try:
            coordinated = await request_service.execute(principal, request)
        except UsageGateError as error:
            messages = {
                "rate_limit_exceeded": "回应太频繁，请稍后再试",
                "daily_quota_exceeded": "今日回应额度已用完",
                "monthly_quota_exceeded": "本月回应额度已用完",
                "global_budget_exhausted": "模型服务本月预算已暂停",
            }
            raise _safe_error(
                error.status_code,
                error.code,
                messages.get(error.code, "额度检查失败"),
            ) from None
        except RequestStateError as error:
            messages = {
                "idempotency_conflict": "requestId 已用于不同内容",
                "request_in_progress": "该请求仍在处理中",
                "request_permanently_failed": "该请求不能继续重试",
                "request_attempt_limit_exceeded": "该请求已达到重试上限",
                "request_outcome_unknown": "供应商结果不确定，该请求已停止自动重试",
            }
            raise _safe_error(
                error.status_code,
                error.code,
                messages.get(error.code, "请求状态冲突"),
            ) from None
        except ValueError as error:
            raise _safe_error(400, "invalid_request", str(error)) from None
        except ProviderError as error:
            safe_status = 429 if error.provider_status == 429 else 502
            if error.provider_status == 402:
                safe_status = 503
            logger.warning(
                "model_request_failed request_id=%s error_category=%s provider_status=%s",
                request.request_id,
                error.code,
                error.provider_status,
            )
            raise _safe_error(
                safe_status,
                error.code,
                "模型服务暂时不可用，请稍后再试",
            ) from None

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if coordinated.replayed:
            logger.info(
                "model_request_replayed request_id=%s principal=%s latency_ms=%s",
                request.request_id,
                provider_user_id(
                    IdentityScope(
                        "user"
                        if principal.principal_type == "user"
                        else "device",
                        principal.id,
                    ),
                    active_settings.provider_user_id_salt,
                ),
                elapsed_ms,
            )
            return coordinated.response

        provider_result = coordinated.provider_result
        assert provider_result is not None
        usage = provider_result.usage
        logger.info(
            "model_request_complete request_id=%s principal=%s provider=%s model=%s "
            "latency_ms=%s input_tokens=%s output_tokens=%s cache_hit_tokens=%s "
            "estimated_cost_cny=%s mode=%s safety_level=%s degraded=%s",
            request.request_id,
            provider_user_id(
                IdentityScope(
                    "user" if principal.principal_type == "user" else "device",
                    principal.id,
                ),
                active_settings.provider_user_id_salt,
            ),
            provider_result.provider,
            provider_result.model,
            elapsed_ms,
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_hit_tokens,
            usage.estimated_cost_cny,
            provider_result.result.mode,
            provider_result.result.safety_level,
            provider_result.degraded,
        )
        return coordinated.response

    return app
