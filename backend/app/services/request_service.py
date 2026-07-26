from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import begin_immediate_if_sqlite
from app.db_models import AssistantProfile, Principal, ReplyRequest
from app.models.reply import NotebookReplyRequest, NotebookReplyResponse
from app.providers.base import ModelResponse, ProviderError
from app.services.reply_service import ReplyService
from app.services.usage_service import UsageService


class RequestStateError(RuntimeError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class CoordinatedReply:
    response: NotebookReplyResponse
    provider_result: ModelResponse | None
    replayed: bool


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def request_fingerprint(request: NotebookReplyRequest) -> str:
    canonical = json.dumps(
        {
            "pageId": request.page_id,
            "recognizedText": request.recognized_text,
            "recognitionSource": request.recognition_source,
            "recentContext": request.recent_context,
            "imageBase64": request.image_base64,
            "deepMode": request.deep_mode,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RequestService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        reply_service: ReplyService,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.reply_service = reply_service
        self.usage_service = UsageService(settings)

    async def execute(
        self, principal: Principal, request: NotebookReplyRequest
    ) -> CoordinatedReply:
        fingerprint = request_fingerprint(request)
        now = datetime.now(timezone.utc)

        with self.session_factory.begin() as session:
            begin_immediate_if_sqlite(session)
            row = session.scalar(
                select(ReplyRequest)
                .where(
                    ReplyRequest.principal_id == principal.id,
                    ReplyRequest.request_id == request.request_id,
                )
                .with_for_update()
            )
            if row is not None:
                if row.request_fingerprint != fingerprint:
                    raise RequestStateError("idempotency_conflict", 409)
                if row.status == "succeeded" and row.response_snapshot:
                    return CoordinatedReply(
                        response=NotebookReplyResponse.model_validate_json(
                            row.response_snapshot
                        ),
                        provider_result=None,
                        replayed=True,
                    )
                if (
                    row.status == "processing"
                    and row.lease_expires_at is not None
                    and _utc(row.lease_expires_at) > now
                ):
                    raise RequestStateError("request_in_progress", 409)
                if row.status == "processing":
                    # The previous worker died after reserving quota. Release
                    # that abandoned reservation before acquiring a fresh lease.
                    self.usage_service.release(session, principal.id)
                if row.status == "permanent_failed":
                    raise RequestStateError("request_permanently_failed", 409)
                if row.attempt_count >= self.settings.request_max_attempts:
                    row.status = "permanent_failed"
                    row.error_category = "attempt_limit_exceeded"
                    raise RequestStateError("request_attempt_limit_exceeded", 409)
            else:
                row = ReplyRequest(
                    principal_id=principal.id,
                    request_id=request.request_id,
                    request_fingerprint=fingerprint,
                    status="pending",
                )
                session.add(row)
                session.flush()

            self.usage_service.reserve(session, principal.id)
            row.status = "processing"
            row.attempt_count += 1
            row.lease_expires_at = now + timedelta(
                seconds=self.settings.request_lease_seconds
            )
            row.error_category = None

        try:
            with self.session_factory() as session:
                profile = session.get(AssistantProfile, principal.id)
                if profile is None:
                    raise RuntimeError("authenticated principal has no profile")
                response, provider_result = await self.reply_service.reply(
                    request,
                    principal=principal,
                    profile=profile,
                )
        except ProviderError as error:
            self._mark_failure(
                principal.id,
                request.request_id,
                error.code,
                retryable=error.retriable,
            )
            raise
        except ValueError:
            self._mark_failure(
                principal.id,
                request.request_id,
                "invalid_request",
                retryable=False,
            )
            raise
        except Exception:
            self._mark_failure(
                principal.id,
                request.request_id,
                "internal_generation_error",
                retryable=True,
            )
            raise

        with self.session_factory.begin() as session:
            begin_immediate_if_sqlite(session)
            row = session.scalar(
                select(ReplyRequest)
                .where(
                    ReplyRequest.principal_id == principal.id,
                    ReplyRequest.request_id == request.request_id,
                )
                .with_for_update()
            )
            if row is None or row.status != "processing":
                raise RequestStateError("request_state_lost", 409)
            usage = provider_result.usage
            self.usage_service.settle(session, principal.id, usage)
            row.status = "succeeded"
            row.lease_expires_at = None
            row.provider = provider_result.provider
            row.model = provider_result.model
            row.input_tokens = usage.input_tokens
            row.output_tokens = usage.output_tokens
            row.cache_tokens = usage.cache_hit_tokens
            row.estimated_cost_cny = usage.estimated_cost_cny
            row.response_snapshot = response.model_dump_json(by_alias=True)
            row.error_category = None
        return CoordinatedReply(
            response=response,
            provider_result=provider_result,
            replayed=False,
        )

    def _mark_failure(
        self,
        principal_id: str,
        request_id: str,
        category: str,
        *,
        retryable: bool,
    ) -> None:
        with self.session_factory.begin() as session:
            begin_immediate_if_sqlite(session)
            row = session.scalar(
                select(ReplyRequest)
                .where(
                    ReplyRequest.principal_id == principal_id,
                    ReplyRequest.request_id == request_id,
                )
                .with_for_update()
            )
            if row is None or row.status != "processing":
                return
            self.usage_service.release(session, principal_id)
            row.status = "retryable_failed" if retryable else "permanent_failed"
            row.error_category = category
            row.lease_expires_at = None
