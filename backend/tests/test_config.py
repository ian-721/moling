from __future__ import annotations

import pytest

from app.config import ConfigurationError, Settings


VALID_API_KEY = "K" * 40
VALID_PROVIDER_SALT = "S" * 32
VALID_TOKEN_PEPPER = "P" * 32
VALID_DATABASE_URL = "postgresql+psycopg://moling@example.invalid/moling"


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "model_provider": "deepseek",
        "deepseek_api_key": VALID_API_KEY,
        "provider_user_id_salt": VALID_PROVIDER_SALT,
        "token_hash_pepper": VALID_TOKEN_PEPPER,
        "database_url": VALID_DATABASE_URL,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_requires_deepseek_secret() -> None:
    with pytest.raises(ConfigurationError, match="DEEPSEEK_API_KEY"):
        production_settings(deepseek_api_key=None).validate()


def test_production_rejects_fake_provider() -> None:
    with pytest.raises(ConfigurationError, match="MODEL_PROVIDER=deepseek"):
        Settings(environment="production", model_provider="fake").validate()


def test_production_rejects_vision_and_image_persistence() -> None:
    with pytest.raises(ConfigurationError, match="Vision"):
        production_settings(vision_fallback_enabled=True).validate()


def test_production_rejects_empty_provider_user_salt() -> None:
    with pytest.raises(ConfigurationError, match="PROVIDER_USER_ID_SALT"):
        production_settings(provider_user_id_salt="").validate()


def test_production_rejects_implicit_limits_and_budget() -> None:
    with pytest.raises(ConfigurationError, match="explicit database"):
        production_settings(
            production_limits_explicit=False,
        ).validate()


def test_production_requires_postgresql() -> None:
    with pytest.raises(ConfigurationError, match="PostgreSQL"):
        production_settings(
            database_url="sqlite:///unsafe-production.db",
        ).validate()


def test_database_url_validation_error_does_not_echo_credentials() -> None:
    password = "synthetic-password-that-must-not-be-printed"
    database_url = (
        f"mysql://railway:{password}@db.example.invalid:3306/moling"
    )
    with pytest.raises(ConfigurationError) as caught:
        production_settings(database_url=database_url).validate()

    message = str(caught.value)
    if password in message or database_url in message:
        pytest.fail(
            "database credentials were included in a configuration error",
            pytrace=False,
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REGISTRATION_ENABLED", "sometimes"),
        ("VISION_FALLBACK_ENABLED", "disabled"),
        ("DEBUG_IMAGE_SAVE_ENABLED", ""),
    ],
)
def test_environment_rejects_ambiguous_boolean_values(
    monkeypatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match=f"{name} must be true or false"):
        Settings.from_env()


@pytest.mark.parametrize(
    "field",
    ["deepseek_api_key", "provider_user_id_salt", "token_hash_pepper"],
)
def test_production_rejects_whitespace_only_secrets(field: str) -> None:
    with pytest.raises(ConfigurationError):
        production_settings(**{field: "   "}).validate()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deepseek_api_key", "ci-placeholder-not-a-secret"),
        ("provider_user_id_salt", "ci-provider-salt-not-a-secret"),
        ("token_hash_pepper", "ci-token-pepper-not-a-secret"),
        ("provider_user_id_salt", "development-only-salt"),
        ("token_hash_pepper", "development-only-token-pepper"),
    ],
)
def test_production_rejects_known_placeholder_secrets(
    field: str, value: str
) -> None:
    with pytest.raises(ConfigurationError, match="placeholder"):
        production_settings(**{field: value}).validate()


@pytest.mark.parametrize(
    "field",
    ["provider_user_id_salt", "token_hash_pepper"],
)
def test_production_requires_32_utf8_bytes_for_hmac_secrets(field: str) -> None:
    with pytest.raises(ConfigurationError, match="at least 32 UTF-8 bytes"):
        production_settings(**{field: "x" * 31}).validate()


@pytest.mark.parametrize(
    "field",
    ["provider_user_id_salt", "token_hash_pepper"],
)
def test_hmac_secret_minimum_counts_utf8_bytes(field: str) -> None:
    production_settings(**{field: "密" * 11}).validate()


@pytest.mark.parametrize(
    "field",
    ["deepseek_api_key", "provider_user_id_salt", "token_hash_pepper"],
)
def test_production_rejects_secret_outer_whitespace(field: str) -> None:
    with pytest.raises(ConfigurationError, match="outer whitespace"):
        production_settings(**{field: f" {VALID_API_KEY} "}).validate()
