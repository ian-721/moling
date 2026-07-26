from __future__ import annotations

from app.config import Settings
from app.models.reply import NotebookReplyRequest, NotebookReplyResponse
from app.providers.base import ModelProvider, ModelRequest, ModelResponse
from app.services.identity_service import (
    build_scope,
    provider_user_id,
    resolve_request_profile,
)
from app.services.prompt_service import build_prompt
from app.services.usage_service import with_estimated_cost


class ReplyService:
    def __init__(self, settings: Settings, provider: ModelProvider) -> None:
        self.settings = settings
        self.provider = provider

    async def reply(self, request: NotebookReplyRequest) -> tuple[NotebookReplyResponse, ModelResponse]:
        recognized_text = (request.recognized_text or "").strip()
        if not recognized_text or recognized_text.upper() == "UNCLEAR":
            raise ValueError("recognizedText is required for the production text path")

        scope = build_scope(request.user_id, request.device_profile_id)
        profile = resolve_request_profile(scope, request.assistant_name)
        prompt = build_prompt(
            profile=profile,
            recognized_text=recognized_text,
            recent_context=request.recent_context,
        )
        result = await self.provider.generate_reply(
            ModelRequest(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
                provider_user_id=provider_user_id(
                    scope, self.settings.provider_user_id_salt
                ),
                prompt_version=prompt.version,
                deep_mode=request.deep_mode,
            )
        )
        usage = with_estimated_cost(
            result.usage,
            deep_mode=result.model == self.settings.deepseek_pro_model,
        )
        result = ModelResponse(
            result=result.result,
            provider=result.provider,
            model=result.model,
            usage=usage,
            degraded=result.degraded,
        )
        response = NotebookReplyResponse(
            requestId=request.request_id,
            recognizedText=recognized_text,
            aiReply=result.result.reply,
            responseMode=result.result.mode,
            recognitionSource=request.recognition_source or "client_text",
            safetyLevel=result.result.safety_level,
            shouldAsk=result.result.should_ask,
            promptVersion=prompt.version,
            provider=result.provider,
            model=result.model,
            degraded=result.degraded,
        )
        return response, result
