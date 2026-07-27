from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised when deployment configuration is unsafe or incomplete."""


MIN_HMAC_SECRET_BYTES = 32
SECRET_PLACEHOLDER_MARKERS = (
    "placeholder",
    "not-a-secret",
    "development-only",
    "change-me",
    "changeme",
)


def _validate_production_secret(
    name: str,
    value: str | None,
    *,
    minimum_bytes: int | None = None,
) -> None:
    if value is None or not value.strip():
        raise ConfigurationError(
            f"Production requires {name} from deployment secrets"
        )
    if value != value.strip():
        raise ConfigurationError(
            f"Production {name} must not contain outer whitespace"
        )
    normalized = value.casefold()
    if any(marker in normalized for marker in SECRET_PLACEHOLDER_MARKERS):
        raise ConfigurationError(
            f"Production {name} must not use a known placeholder value"
        )
    if minimum_bytes is not None and len(value.encode("utf-8")) < minimum_bytes:
        raise ConfigurationError(
            f"Production {name} must be at least {minimum_bytes} UTF-8 bytes"
        )


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _as_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _as_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    model_provider: str = "fake"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    default_max_tokens: int = 420
    deep_max_tokens: int = 800
    timeout_seconds: float = 40.0
    retry_count: int = 1
    provider_user_id_salt: str = "development-only-salt"
    vision_fallback_enabled: bool = False
    debug_image_save_enabled: bool = False
    log_level: str = "INFO"
    database_url: str = "sqlite:///./moling.db"
    token_hash_pepper: str = "development-only-token-pepper"
    access_token_ttl_seconds: int = 2_592_000
    registration_enabled: bool = True
    registration_requests_per_minute: int = 30
    registration_max_principals: int = 10_000
    principal_requests_per_minute: int = 10
    principal_daily_request_limit: int = 50
    principal_monthly_request_limit: int = 500
    global_monthly_budget_cny: float = 300.0
    request_lease_seconds: int = 90
    request_max_attempts: int = 3
    request_cost_reservation_cny: float = 0.05
    production_limits_explicit: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @classmethod
    def from_env(cls) -> "Settings":
        production_limit_names = {
            "DATABASE_URL",
            "TOKEN_HASH_PEPPER",
            "ACCESS_TOKEN_TTL_SECONDS",
            "REGISTRATION_ENABLED",
            "REGISTRATION_REQUESTS_PER_MINUTE",
            "REGISTRATION_MAX_PRINCIPALS",
            "PRINCIPAL_REQUESTS_PER_MINUTE",
            "PRINCIPAL_DAILY_REQUEST_LIMIT",
            "PRINCIPAL_MONTHLY_REQUEST_LIMIT",
            "GLOBAL_MONTHLY_BUDGET_CNY",
            "REQUEST_LEASE_SECONDS",
            "REQUEST_MAX_ATTEMPTS",
            "REQUEST_COST_RESERVATION_CNY",
        }
        settings = cls(
            environment=os.getenv("MOLING_ENV", "development"),
            model_provider=os.getenv("MODEL_PROVIDER", "fake"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/"),
            deepseek_flash_model=os.getenv(
                "DEEPSEEK_FLASH_MODEL", "deepseek-v4-flash"
            ),
            deepseek_pro_model=os.getenv(
                "DEEPSEEK_PRO_MODEL", "deepseek-v4-pro"
            ),
            default_max_tokens=int(
                os.getenv("DEEPSEEK_DEFAULT_MAX_TOKENS", "420")
            ),
            deep_max_tokens=int(os.getenv("DEEPSEEK_DEEP_MAX_TOKENS", "800")),
            timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "40")),
            retry_count=int(os.getenv("DEEPSEEK_RETRY_COUNT", "1")),
            provider_user_id_salt=os.getenv(
                "PROVIDER_USER_ID_SALT", "development-only-salt"
            ),
            vision_fallback_enabled=_as_bool("VISION_FALLBACK_ENABLED", False),
            debug_image_save_enabled=_as_bool("DEBUG_IMAGE_SAVE_ENABLED", False),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./moling.db"),
            token_hash_pepper=os.getenv(
                "TOKEN_HASH_PEPPER", "development-only-token-pepper"
            ),
            access_token_ttl_seconds=_as_int("ACCESS_TOKEN_TTL_SECONDS", 2_592_000),
            registration_enabled=_as_bool("REGISTRATION_ENABLED", True),
            registration_requests_per_minute=_as_int(
                "REGISTRATION_REQUESTS_PER_MINUTE", 30
            ),
            registration_max_principals=_as_int(
                "REGISTRATION_MAX_PRINCIPALS", 10_000
            ),
            principal_requests_per_minute=_as_int(
                "PRINCIPAL_REQUESTS_PER_MINUTE", 10
            ),
            principal_daily_request_limit=_as_int(
                "PRINCIPAL_DAILY_REQUEST_LIMIT", 50
            ),
            principal_monthly_request_limit=_as_int(
                "PRINCIPAL_MONTHLY_REQUEST_LIMIT", 500
            ),
            global_monthly_budget_cny=_as_float(
                "GLOBAL_MONTHLY_BUDGET_CNY", 300.0
            ),
            request_lease_seconds=_as_int("REQUEST_LEASE_SECONDS", 90),
            request_max_attempts=_as_int("REQUEST_MAX_ATTEMPTS", 3),
            request_cost_reservation_cny=_as_float(
                "REQUEST_COST_RESERVATION_CNY", 0.05
            ),
            production_limits_explicit=all(
                os.getenv(name) is not None for name in production_limit_names
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.model_provider not in {"deepseek", "fake"}:
            raise ConfigurationError("MODEL_PROVIDER must be deepseek or fake")
        if self.retry_count not in {0, 1}:
            raise ConfigurationError("DEEPSEEK_RETRY_COUNT must be 0 or 1")
        if self.default_max_tokens <= 0 or self.deep_max_tokens <= 0:
            raise ConfigurationError("DeepSeek max token limits must be positive")
        if not self.database_url:
            raise ConfigurationError("DATABASE_URL must not be empty")
        positive_limits = {
            "ACCESS_TOKEN_TTL_SECONDS": self.access_token_ttl_seconds,
            "REGISTRATION_REQUESTS_PER_MINUTE": self.registration_requests_per_minute,
            "REGISTRATION_MAX_PRINCIPALS": self.registration_max_principals,
            "PRINCIPAL_REQUESTS_PER_MINUTE": self.principal_requests_per_minute,
            "PRINCIPAL_DAILY_REQUEST_LIMIT": self.principal_daily_request_limit,
            "PRINCIPAL_MONTHLY_REQUEST_LIMIT": self.principal_monthly_request_limit,
            "GLOBAL_MONTHLY_BUDGET_CNY": self.global_monthly_budget_cny,
            "REQUEST_LEASE_SECONDS": self.request_lease_seconds,
            "REQUEST_MAX_ATTEMPTS": self.request_max_attempts,
            "REQUEST_COST_RESERVATION_CNY": self.request_cost_reservation_cny,
        }
        invalid = [name for name, value in positive_limits.items() if value <= 0]
        if invalid:
            raise ConfigurationError(
                f"Quota and token settings must be positive: {', '.join(invalid)}"
            )
        if self.deepseek_flash_model != "deepseek-v4-flash":
            raise ConfigurationError(
                "DEEPSEEK_FLASH_MODEL must be deepseek-v4-flash for M0-A"
            )
        if self.deepseek_pro_model != "deepseek-v4-pro":
            raise ConfigurationError(
                "DEEPSEEK_PRO_MODEL must be deepseek-v4-pro for M0-A"
            )

        base_url = urlparse(self.deepseek_base_url)
        if base_url.scheme != "https" or not base_url.netloc:
            raise ConfigurationError("DEEPSEEK_BASE_URL must be an HTTPS URL")

        if self.is_production:
            if not self.production_limits_explicit:
                raise ConfigurationError(
                    "Production requires explicit database, token TTL, registration, "
                    "rate, quota, lease, and budget configuration"
                )
            if self.model_provider != "deepseek":
                raise ConfigurationError(
                    "Production requires MODEL_PROVIDER=deepseek"
                )
            _validate_production_secret(
                "DEEPSEEK_API_KEY",
                self.deepseek_api_key,
            )
            _validate_production_secret(
                "PROVIDER_USER_ID_SALT",
                self.provider_user_id_salt,
                minimum_bytes=MIN_HMAC_SECRET_BYTES,
            )
            if self.vision_fallback_enabled or self.debug_image_save_enabled:
                raise ConfigurationError(
                    "Production must disable Vision fallback and image persistence"
                )
            _validate_production_secret(
                "TOKEN_HASH_PEPPER",
                self.token_hash_pepper,
                minimum_bytes=MIN_HMAC_SECRET_BYTES,
            )
            if not (
                self.database_url.startswith("postgresql://")
                or self.database_url.startswith("postgresql+psycopg://")
            ):
                raise ConfigurationError(
                    "Production DATABASE_URL must use PostgreSQL"
                )
