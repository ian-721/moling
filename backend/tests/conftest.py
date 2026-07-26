from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        model_provider="fake",
        provider_user_id_salt="test-salt-not-a-secret",
        token_hash_pepper="test-token-pepper-not-a-secret",
        database_url="sqlite:///:memory:",
    )
