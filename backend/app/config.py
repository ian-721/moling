from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised when deployment configuration is unsafe or incomplete."""


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @classmethod
    def from_env(cls) -> "Settings":
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
            vision_fallback_enabled=_as_bool(
                os.getenv("VISION_FALLBACK_ENABLED"), False
            ),
            debug_image_save_enabled=_as_bool(
                os.getenv("DEBUG_IMAGE_SAVE_ENABLED"), False
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
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
            if self.model_provider != "deepseek":
                raise ConfigurationError(
                    "Production requires MODEL_PROVIDER=deepseek"
                )
            if not self.deepseek_api_key:
                raise ConfigurationError(
                    "Production requires DEEPSEEK_API_KEY from deployment secrets"
                )
            if (
                not self.provider_user_id_salt
                or self.provider_user_id_salt == "development-only-salt"
            ):
                raise ConfigurationError(
                    "Production requires a secret PROVIDER_USER_ID_SALT"
                )
            if self.vision_fallback_enabled or self.debug_image_save_enabled:
                raise ConfigurationError(
                    "Production must disable Vision fallback and image persistence"
                )
