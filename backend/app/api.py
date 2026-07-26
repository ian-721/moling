from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings
from app.models.reply import NotebookReplyRequest, NotebookReplyResponse
from app.providers.base import ModelProvider, ProviderError
from app.providers.deepseek import DeepSeekProvider
from app.providers.fake import FakeProvider
from app.services.identity_service import build_scope, provider_user_id
from app.services.reply_service import ReplyService

logger = logging.getLogger("moling.api")


def _provider_for(settings: Settings) -> ModelProvider:
    if settings.model_provider == "deepseek":
        return DeepSeekProvider(settings)
    return FakeProvider()


def create_app(
    *,
    settings: Settings | None = None,
    provider: ModelProvider | None = None,
) -> FastAPI:
    active_settings = settings or Settings.from_env()
    active_provider = provider or _provider_for(active_settings)
    service = ReplyService(active_settings, active_provider)

    logging.basicConfig(
        level=getattr(logging, active_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        close = getattr(active_provider, "close", None)
        if close is not None:
            await close()

    app = FastAPI(
        title="Moling API",
        version="0.8.0-m0a",
        lifespan=lifespan,
    )

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

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "environment": active_settings.environment,
            "provider": active_settings.model_provider,
        }

    @app.post("/api/notebook/reply", response_model=NotebookReplyResponse)
    async def notebook_reply(
        request: NotebookReplyRequest,
    ) -> NotebookReplyResponse:
        started = time.perf_counter()
        if request.image_base64:
            if not active_settings.vision_fallback_enabled:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "vision_disabled",
                        "message": "Vision fallback is disabled",
                    },
                )
            raise HTTPException(
                status_code=501,
                detail={
                    "code": "vision_not_configured",
                    "message": "Vision fallback has no production provider",
                },
            )
        try:
            response, provider_result = await service.reply(request)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_request", "message": str(error)},
            ) from None
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
            raise HTTPException(
                status_code=safe_status,
                detail={
                    "code": error.code,
                    "message": "模型服务暂时不可用，请稍后再试",
                },
            ) from None

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        usage = provider_result.usage
        anonymous_subject = provider_user_id(
            build_scope(request.user_id, request.device_profile_id),
            active_settings.provider_user_id_salt,
        )
        logger.info(
            "model_request_complete request_id=%s anonymous_subject=%s provider=%s model=%s "
            "latency_ms=%s input_tokens=%s output_tokens=%s cache_hit_tokens=%s "
            "estimated_cost_cny=%s mode=%s safety_level=%s degraded=%s",
            request.request_id,
            anonymous_subject,
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
        return response

    return app
