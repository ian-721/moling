from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_m0b_migration_upgrades_clean_database(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert {
        "principals",
        "device_installations",
        "access_tokens",
        "assistant_profiles",
        "usage_windows",
        "global_budget_windows",
        "reply_requests",
        "registration_windows",
        "alembic_version",
    } <= tables
    columns = {
        column["name"]
        for column in inspect(create_engine(database_url)).get_columns(
            "reply_requests"
        )
    }
    assert {
        "provider_started_at",
        "reservation_day_start",
        "reservation_month_start",
        "budget_month_start",
        "reserved_cost_cny",
        "reservation_state",
    } <= columns
    command.check(config)


def test_m0b1_migration_upgrades_existing_m0b_database(
    tmp_path, monkeypatch
) -> None:
    database_path = tmp_path / "existing.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "20260726_0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO principals "
                "(id, principal_type, status, created_at, updated_at) "
                "VALUES ('p1', 'device', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO reply_requests "
                "(id, principal_id, request_id, request_fingerprint, status, "
                "attempt_count, input_tokens, output_tokens, cache_tokens, "
                "estimated_cost_cny, created_at, updated_at) VALUES "
                "('r1', 'p1', 'request-old', 'fingerprint', 'processing', "
                "1, 0, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        status = connection.execute(
            text("SELECT status FROM reply_requests WHERE id='r1'")
        ).scalar_one()
    assert status == "outcome_unknown"
    command.check(config)
