from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import begin_immediate_if_sqlite
from app.db_models import (
    AccessToken,
    AssistantProfile,
    DeviceInstallation,
    Principal,
    RegistrationWindow,
)
from app.services.identity_service import DEFAULT_ASSISTANT_NAME


class AuthenticationError(RuntimeError):
    pass


class RegistrationError(RuntimeError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class IssuedSession:
    principal: Principal
    profile: AssistantProfile
    raw_token: str
    expires_at: datetime


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _minute_start(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


class AuthService:
    def __init__(
        self, settings: Settings, session_factory: sessionmaker[Session]
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def _digest(self, purpose: str, raw: str) -> str:
        return hmac.new(
            self.settings.token_hash_pepper.encode("utf-8"),
            f"{purpose}:{raw}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def token_hash(self, raw_token: str) -> str:
        return self._digest("access-token", raw_token)

    def installation_hash(self, installation_id: str) -> str:
        return self._digest("installation", installation_id)

    def authenticate(self, raw_token: str | None) -> Principal:
        if not raw_token:
            raise AuthenticationError("missing_access_token")
        token_hash = self.token_hash(raw_token)
        now = datetime.now(timezone.utc)
        with self.session_factory.begin() as session:
            token = session.scalar(
                select(AccessToken)
                .where(AccessToken.token_hash == token_hash)
                .with_for_update()
            )
            if (
                token is None
                or token.revoked_at is not None
                or _utc(token.expires_at) <= now
            ):
                raise AuthenticationError("invalid_access_token")
            principal = session.get(Principal, token.principal_id)
            if principal is None or principal.status != "active":
                raise AuthenticationError("invalid_access_token")
            token.last_used_at = now
            return principal

    def register_device(
        self,
        installation_id: str,
        *,
        rotation_principal_id: str | None = None,
    ) -> IssuedSession:
        if not self.settings.registration_enabled:
            raise RegistrationError("registration_disabled", 503)
        now = datetime.now(timezone.utc)
        installation_hash = self.installation_hash(installation_id)
        raw_token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(seconds=self.settings.access_token_ttl_seconds)

        try:
            with self.session_factory.begin() as session:
                begin_immediate_if_sqlite(session)
                window_start = _minute_start(now)
                window = session.get(
                    RegistrationWindow, window_start, with_for_update=True
                )
                if window is None:
                    window = RegistrationWindow(window_start=window_start)
                    session.add(window)
                    session.flush()
                if (
                    window.request_count
                    >= self.settings.registration_requests_per_minute
                ):
                    raise RegistrationError("registration_rate_limited", 429)
                window.request_count += 1

                installation = session.scalar(
                    select(DeviceInstallation)
                    .where(
                        DeviceInstallation.installation_hash == installation_hash
                    )
                    .with_for_update()
                )
                if installation is not None:
                    if (
                        installation.revoked_at is not None
                        or rotation_principal_id != installation.principal_id
                    ):
                        raise RegistrationError(
                            "installation_already_registered", 409
                        )
                    principal = session.get(Principal, installation.principal_id)
                    if principal is None or principal.status != "active":
                        raise RegistrationError("installation_revoked", 401)
                    session.query(AccessToken).filter(
                        AccessToken.principal_id == principal.id,
                        AccessToken.revoked_at.is_(None),
                    ).update({AccessToken.revoked_at: now})
                    installation.last_seen_at = now
                else:
                    principal_count = session.scalar(
                        select(func.count()).select_from(Principal)
                    )
                    if (
                        principal_count is not None
                        and principal_count
                        >= self.settings.registration_max_principals
                    ):
                        raise RegistrationError("registration_capacity_reached", 503)
                    principal = Principal(principal_type="device", status="active")
                    session.add(principal)
                    session.flush()
                    installation = DeviceInstallation(
                        principal_id=principal.id,
                        installation_hash=installation_hash,
                        last_seen_at=now,
                    )
                    session.add(installation)
                    session.add(
                        AssistantProfile(
                            principal_id=principal.id,
                            assistant_name=DEFAULT_ASSISTANT_NAME,
                        )
                    )

                session.add(
                    AccessToken(
                        principal_id=principal.id,
                        token_hash=self.token_hash(raw_token),
                        expires_at=expires_at,
                    )
                )
                session.flush()
                profile = session.get(AssistantProfile, principal.id)
                assert profile is not None
                return IssuedSession(
                    principal=principal,
                    profile=profile,
                    raw_token=raw_token,
                    expires_at=expires_at,
                )
        except IntegrityError as error:
            raise RegistrationError("registration_conflict", 409) from error
