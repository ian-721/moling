from __future__ import annotations

import json
from pathlib import Path


def test_public_persona_golden_cases_have_minimum_schema() -> None:
    path = (
        Path(__file__).resolve().parent
        / "persona_cases"
        / "public_golden_cases_v1.jsonl"
    )
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(cases) >= 3
    for case in cases:
        assert case["input"]
        assert case["must_do"]
        assert case["must_not_do"]
        assert case["reference_traits"]
