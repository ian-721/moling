from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Literal, Protocol

DEFAULT_ASSISTANT_NAME = "墨灵"
VALID_ID = re.compile(r"^[A-Za-z0-9._:-]+$")
DEEPSEEK_USER_ID_MAX_LENGTH = 512
PROVIDER_USER_ID_PATTERN = re.compile(
    rf"^[A-Za-z0-9_-]{{1,{DEEPSEEK_USER_ID_MAX_LENGTH}}}$"
)


@dataclass(frozen=True)
class IdentityScope:
    kind: Literal["user", "device"]
    subject_id: str

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, self.subject_id


@dataclass(frozen=True)
class AssistantProfile:
    scope: IdentityScope
    assistant_name: str


class ScopedProfileStore(Protocol):
    def get(self, scope: IdentityScope) -> AssistantProfile | None:
        """Read a profile only by authenticated user or anonymous device scope."""


def build_scope(user_id: str | None, device_profile_id: str | None) -> IdentityScope:
    raw = user_id or device_profile_id
    if raw is None or not VALID_ID.fullmatch(raw):
        raise ValueError("identity contains unsupported characters")
    return IdentityScope("user" if user_id else "device", raw)


def normalize_assistant_name(value: str | None) -> str:
    if value is None:
        return DEFAULT_ASSISTANT_NAME
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > 16:
        return DEFAULT_ASSISTANT_NAME
    if any(ord(char) < 32 for char in normalized):
        return DEFAULT_ASSISTANT_NAME
    return normalized


def validate_assistant_name(value: str | None) -> str:
    if value is None:
        raise ValueError("assistant_name is required")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("assistant_name must not be blank")
    if len(normalized) > 16:
        raise ValueError("assistant_name is too long")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ValueError("assistant_name contains control characters")
    return normalized


def resolve_request_profile(
    scope: IdentityScope, assistant_name: str | None
) -> AssistantProfile:
    # M0-A has no account database yet. Keeping scope mandatory here prevents a
    # future store from ever using assistant_name as a lookup key.
    return AssistantProfile(
        scope=scope,
        assistant_name=normalize_assistant_name(assistant_name),
    )


def provider_user_id(scope: IdentityScope, salt: str) -> str:
    digest = hmac.new(
        salt.encode("utf-8"),
        f"{scope.kind}:{scope.subject_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    anonymous_id = f"moling_{digest[:32]}"
    if not PROVIDER_USER_ID_PATTERN.fullmatch(anonymous_id):
        raise ValueError("generated provider user id violates DeepSeek constraints")
    return anonymous_id
