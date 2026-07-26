from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
    command.check(config)
