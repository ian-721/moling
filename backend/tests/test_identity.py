from __future__ import annotations

import inspect

from app.services.identity_service import (
    DEEPSEEK_USER_ID_MAX_LENGTH,
    IdentityScope,
    PROVIDER_USER_ID_PATTERN,
    ScopedProfileStore,
    normalize_assistant_name,
    provider_user_id,
    resolve_request_profile,
)


def test_invalid_name_falls_back() -> None:
    assert normalize_assistant_name("   ") == "墨灵"
    assert normalize_assistant_name("\n") == "墨灵"


def test_provider_ids_are_scoped_not_named() -> None:
    first = provider_user_id(IdentityScope("user", "user-a"), "salt")
    second = provider_user_id(IdentityScope("user", "user-b"), "salt")
    assert first != second
    assert "user-a" not in first
    assert "user-b" not in second
    assert PROVIDER_USER_ID_PATTERN.fullmatch(first)
    assert PROVIDER_USER_ID_PATTERN.fullmatch(second)
    assert len(first) <= DEEPSEEK_USER_ID_MAX_LENGTH
    assert len(second) <= DEEPSEEK_USER_ID_MAX_LENGTH


def test_same_assistant_name_does_not_affect_provider_id_isolation() -> None:
    first_scope = IdentityScope("user", "user-a")
    second_scope = IdentityScope("user", "user-b")
    first_profile = resolve_request_profile(first_scope, "老g")
    second_profile = resolve_request_profile(second_scope, "老g")

    assert first_profile.assistant_name == second_profile.assistant_name
    assert provider_user_id(first_profile.scope, "salt") != provider_user_id(
        second_profile.scope,
        "salt",
    )


def test_profile_store_contract_cannot_read_by_name() -> None:
    signature = inspect.signature(ScopedProfileStore.get)
    assert list(signature.parameters) == ["self", "scope"]
