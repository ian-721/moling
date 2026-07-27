from __future__ import annotations

import pytest

from app.config import Settings, normalize_database_url
from app.database import create_database_engine


def _assert_database_url_equal(actual: str, expected: str) -> None:
    if actual != expected:
        pytest.fail("database URL normalization mismatch", pytrace=False)


def _assert_database_url_not_disclosed(
    output: str,
    *,
    password: str,
    database_url: str,
) -> None:
    if password in output or database_url in output:
        pytest.fail("database credentials were written to test output", pytrace=False)


def test_normalizes_standard_postgresql_url_to_psycopg_3() -> None:
    _assert_database_url_equal(
        normalize_database_url("postgresql://moling@example.invalid/moling"),
        "postgresql+psycopg://moling@example.invalid/moling",
    )


def test_preserves_explicit_psycopg_url() -> None:
    value = "postgresql+psycopg://moling@example.invalid/moling"
    _assert_database_url_equal(normalize_database_url(value), value)


def test_preserves_sqlite_urls() -> None:
    values = (
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///./moling.db",
    )
    for value in values:
        _assert_database_url_equal(normalize_database_url(value), value)


def test_preserves_unknown_database_url_schemes_and_values() -> None:
    values = (
        "mysql://moling@example.invalid/moling",
        "not-a-database-url",
        "",
    )
    for value in values:
        _assert_database_url_equal(normalize_database_url(value), value)


def test_only_changes_scheme_with_percent_encoded_credentials() -> None:
    value = (
        "postgresql://railway:p%40ss%25word%2Fpart@db.example.invalid:5432/moling"
    )
    expected = (
        "postgresql+psycopg://"
        "railway:p%40ss%25word%2Fpart@db.example.invalid:5432/moling"
    )
    _assert_database_url_equal(normalize_database_url(value), expected)


def test_only_changes_scheme_with_query_and_fragment() -> None:
    value = (
        "postgresql://railway@db.example.invalid:5432/moling"
        "?sslmode=require&fallback=postgresql://replica.invalid/moling"
        "&application_name=moling%20backend#deployment"
    )
    expected = (
        "postgresql+psycopg://railway@db.example.invalid:5432/moling"
        "?sslmode=require&fallback=postgresql://replica.invalid/moling"
        "&application_name=moling%20backend#deployment"
    )
    _assert_database_url_equal(normalize_database_url(value), expected)


def test_settings_from_env_normalizes_standard_postgresql_url(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MOLING_ENV", "development")
    monkeypatch.setenv("MODEL_PROVIDER", "fake")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://moling@example.invalid/moling",
    )

    settings = Settings.from_env()

    _assert_database_url_equal(
        settings.database_url,
        "postgresql+psycopg://moling@example.invalid/moling",
    )


def test_create_database_engine_uses_psycopg_3_for_standard_postgresql_url(
    capsys,
    caplog,
) -> None:
    password = "synthetic-password-that-must-not-be-printed"
    database_url = (
        f"postgresql://railway:{password}@db.example.invalid:5432/moling"
    )
    engine = create_database_engine(Settings(database_url=database_url))
    try:
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()

    captured = capsys.readouterr()
    for output in (captured.out, captured.err, caplog.text):
        _assert_database_url_not_disclosed(
            output,
            password=password,
            database_url=database_url,
        )


def test_database_engine_url_error_does_not_disclose_credentials(
    capsys,
    caplog,
) -> None:
    password = "synthetic-password-that-must-not-be-printed"
    database_url = (
        f"postgresql://railway:{password}@db.example.invalid:bad-port/moling"
    )

    with pytest.raises(ValueError) as caught:
        create_database_engine(Settings(database_url=database_url))

    captured = capsys.readouterr()
    for output in (
        str(caught.value),
        captured.out,
        captured.err,
        caplog.text,
    ):
        _assert_database_url_not_disclosed(
            output,
            password=password,
            database_url=database_url,
        )
