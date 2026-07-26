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
