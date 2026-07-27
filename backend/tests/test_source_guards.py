from __future__ import annotations

from pathlib import Path


def test_production_source_has_no_retired_models_or_openai_responses() -> None:
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "app").rglob("*.py")
    )
    retired = "deepseek" + "-chat"
    retired_reasoner = "deepseek" + "-reasoner"
    assert retired not in source
    assert retired_reasoner not in source
    assert ".responses.create" not in source


def test_no_runtime_image_write_path() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "write_bytes" not in source
    assert "debug_last_request" not in source


def test_deepseek_payload_uses_user_id_not_legacy_user() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "providers" / "deepseek.py").read_text(
        encoding="utf-8"
    )
    assert '"user_id": request.provider_user_id' in source
    assert '"user": request.provider_user_id' not in source


def test_backend_uses_psycopg_3_without_psycopg2() -> None:
    root = Path(__file__).resolve().parents[1]
    production_requirements = (root / "requirements.txt").read_text(
        encoding="utf-8"
    )
    development_requirements = (root / "requirements-dev.txt").read_text(
        encoding="utf-8"
    )
    combined_requirements = (
        production_requirements + "\n" + development_requirements
    ).lower()
    assert "psycopg[binary]" in production_requirements.lower()
    assert "psycopg2" not in combined_requirements


def test_postgresql_ci_migration_uses_standard_railway_scheme() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    migration_step = workflow.split("- name: Run migration smoke", 1)[1].split(
        "- name:", 1
    )[0]
    uses_standard_scheme = (
        "DATABASE_URL: postgresql://moling@localhost:5432/moling_ci"
        in migration_step
    )
    uses_explicit_driver = "postgresql+psycopg://" in migration_step
    if not uses_standard_scheme or uses_explicit_driver:
        raise AssertionError(
            "PostgreSQL migration smoke must use the standard Railway scheme"
        )
