from __future__ import annotations

import inspect

from app.services.identity_service import (
    IdentityScope,
    ScopedProfileStore,
    normalize_assistant_name,
    provider_user_id,
)


def test_invalid_name_falls_back() -> None:
    assert normalize_assistant_name("   ") == "墨灵"
    assert normalize_assistant_name("\n") == "墨灵"


def test_provider_ids_are_scoped_not_named() -> None:
    first = provider_user_id(IdentityScope("user", "user-a"), "salt")
    second = provider_user_id(IdentityScope("user", "user-b"), "salt")
    assert first != second
    assert "user-a" not in first


def test_profile_store_contract_cannot_read_by_name() -> None:
    signature = inspect.signature(ScopedProfileStore.get)
    assert list(signature.parameters) == ["self", "scope"]
