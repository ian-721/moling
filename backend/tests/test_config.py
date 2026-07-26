from __future__ import annotations

import pytest

from app.config import ConfigurationError, Settings


def test_production_requires_deepseek_secret() -> None:
    with pytest.raises(ConfigurationError, match="DEEPSEEK_API_KEY"):
        Settings(
            environment="production",
            model_provider="deepseek",
            provider_user_id_salt="real-deployment-salt",
        ).validate()


def test_production_rejects_fake_provider() -> None:
    with pytest.raises(ConfigurationError, match="MODEL_PROVIDER=deepseek"):
        Settings(environment="production", model_provider="fake").validate()


def test_production_rejects_vision_and_image_persistence() -> None:
    with pytest.raises(ConfigurationError, match="Vision"):
        Settings(
            environment="production",
            model_provider="deepseek",
            deepseek_api_key="test-placeholder",
            provider_user_id_salt="deployment-secret-placeholder",
            vision_fallback_enabled=True,
        ).validate()


def test_production_rejects_empty_provider_user_salt() -> None:
    with pytest.raises(ConfigurationError, match="PROVIDER_USER_ID_SALT"):
        Settings(
            environment="production",
            model_provider="deepseek",
            deepseek_api_key="test-placeholder",
            provider_user_id_salt="",
        ).validate()


def test_production_rejects_implicit_limits_and_budget() -> None:
    with pytest.raises(ConfigurationError, match="explicit database"):
        Settings(
            environment="production",
            model_provider="deepseek",
            deepseek_api_key="test-placeholder",
            provider_user_id_salt="deployment-secret-placeholder",
            token_hash_pepper="deployment-token-pepper-placeholder",
            database_url="postgresql+psycopg://example.invalid/moling",
            production_limits_explicit=False,
        ).validate()


def test_production_requires_postgresql() -> None:
    with pytest.raises(ConfigurationError, match="PostgreSQL"):
        Settings(
            environment="production",
            model_provider="deepseek",
            deepseek_api_key="test-placeholder",
            provider_user_id_salt="deployment-secret-placeholder",
            token_hash_pepper="deployment-token-pepper-placeholder",
            database_url="sqlite:///unsafe-production.db",
        ).validate()
