from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        model_provider="fake",
        provider_user_id_salt="test-salt-not-a-secret",
    )
