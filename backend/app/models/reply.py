from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReplyMode = Literal[
    "companion",
    "mirror",
    "judgment",
    "root_cause",
    "decision",
    "execution",
    "grounding",
    "challenge",
    "quiet",
    "safety",
]
SafetyLevel = Literal["normal", "elevated", "critical"]


class GeneratedReply(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    mode: ReplyMode
    safety_level: SafetyLevel
    should_ask: bool
    memory_candidates: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("reply")
    @classmethod
    def reply_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reply must not be blank")
        return value

    @field_validator("memory_candidates")
    @classmethod
    def bound_memory_candidates(cls, value: list[str]) -> list[str]:
        if any(len(item) > 240 for item in value):
            raise ValueError("memory candidate too long")
        return value


class NotebookReplyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    request_id: str = Field(
        default_factory=lambda: str(uuid4()), alias="requestId", min_length=8, max_length=128
    )
    page_id: str | None = Field(default=None, alias="pageId", max_length=128)
    recognized_text: str | None = Field(
        default=None, alias="recognizedText", max_length=3000
    )
    recognition_source: str | None = Field(
        default=None, alias="recognitionSource", max_length=64
    )
    recent_context: str | None = Field(
        default=None, alias="recentContext", max_length=6000
    )
    image_base64: str | None = Field(default=None, alias="imageBase64")
    deep_mode: bool = Field(default=False, alias="deepMode")



class NotebookReplyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    request_id: str = Field(alias="requestId")
    recognized_text: str = Field(alias="recognizedText")
    ai_reply: str = Field(alias="aiReply")
    response_mode: ReplyMode = Field(alias="responseMode")
    recognition_source: str = Field(alias="recognitionSource")
    safety_level: SafetyLevel = Field(alias="safetyLevel")
    should_ask: bool = Field(alias="shouldAsk")
    prompt_version: str = Field(alias="promptVersion")
    provider: str
    model: str
    degraded: bool = False
