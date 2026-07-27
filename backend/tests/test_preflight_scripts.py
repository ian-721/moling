from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import android_release_preflight as android_preflight  # noqa: E402
from scripts import deployment_preflight  # noqa: E402
from scripts import remote_https_smoke as remote_smoke  # noqa: E402


@pytest.fixture
def production_environment(monkeypatch) -> None:
    values = {
        "MOLING_ENV": "production",
        "MODEL_PROVIDER": "deepseek",
        "DATABASE_URL": "postgresql+psycopg://moling@example.invalid/moling",
        "DEEPSEEK_API_KEY": "K" * 40,
        "PROVIDER_USER_ID_SALT": "S" * 32,
        "TOKEN_HASH_PEPPER": "P" * 32,
        "ACCESS_TOKEN_TTL_SECONDS": "2592000",
        "REGISTRATION_ENABLED": "true",
        "REGISTRATION_REQUESTS_PER_MINUTE": "30",
        "REGISTRATION_MAX_PRINCIPALS": "10000",
        "PRINCIPAL_REQUESTS_PER_MINUTE": "10",
        "PRINCIPAL_DAILY_REQUEST_LIMIT": "50",
        "PRINCIPAL_MONTHLY_REQUEST_LIMIT": "500",
        "GLOBAL_MONTHLY_BUDGET_CNY": "300",
        "REQUEST_LEASE_SECONDS": "90",
        "REQUEST_MAX_ATTEMPTS": "3",
        "REQUEST_COST_RESERVATION_CNY": "0.05",
        "VISION_FALLBACK_ENABLED": "false",
        "DEBUG_IMAGE_SAVE_ENABLED": "false",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_deployment_preflight_rejects_public_placeholder_without_echoing_it(
    monkeypatch,
    production_environment,
    capsys,
) -> None:
    public_value = "ci-provider-salt-not-a-secret"
    monkeypatch.setenv("PROVIDER_USER_ID_SALT", public_value)
    assert deployment_preflight.main() == 1
    captured = capsys.readouterr()
    assert "placeholder" in captured.err
    assert public_value not in captured.err


def test_deployment_preflight_rejects_short_hmac_secret(
    monkeypatch,
    production_environment,
    capsys,
) -> None:
    monkeypatch.setenv("TOKEN_HASH_PEPPER", "x" * 31)
    assert deployment_preflight.main() == 1
    assert "at least 32 UTF-8 bytes" in capsys.readouterr().err


def test_deployment_preflight_rejects_ambiguous_boolean(
    monkeypatch,
    production_environment,
    capsys,
) -> None:
    monkeypatch.setenv("REGISTRATION_ENABLED", "sometimes")
    assert deployment_preflight.main() == 1
    assert "must be true or false" in capsys.readouterr().err


def _clear_android_environment(monkeypatch) -> None:
    monkeypatch.delenv("MOLING_RELEASE_BACKEND_URL", raising=False)
    for name in android_preflight.SIGNING_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _set_complete_signing_environment(monkeypatch, tmp_path: Path) -> None:
    keystore = tmp_path / "synthetic-test-file.jks"
    keystore.write_bytes(b"not-a-real-keystore")
    values = {
        "MOLING_KEYSTORE_PATH": str(keystore),
        "MOLING_KEYSTORE_PASSWORD": "synthetic-test-password",
        "MOLING_KEY_ALIAS": "synthetic-test-alias",
        "MOLING_KEY_PASSWORD": "synthetic-test-password",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_android_preflight_rejects_partial_signing(
    monkeypatch,
    capsys,
) -> None:
    _clear_android_environment(monkeypatch)
    monkeypatch.setenv("MOLING_KEY_ALIAS", "only-one-value")
    monkeypatch.setattr(
        sys,
        "argv",
        ["android_release_preflight.py", "--backend-url", "https://release.invalid"],
    )
    assert android_preflight.main() == 1
    assert "signing is partial" in capsys.readouterr().err


def test_android_preflight_rejects_signed_build_without_explicit_url(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    _clear_android_environment(monkeypatch)
    _set_complete_signing_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["android_release_preflight.py", "--require-signing"],
    )
    assert android_preflight.main() == 1
    assert "backend-url is required" in capsys.readouterr().err


def test_android_preflight_rejects_signed_invalid_hostname(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    _clear_android_environment(monkeypatch)
    _set_complete_signing_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "android_release_preflight.py",
            "--backend-url",
            "https://release.invalid",
            "--require-signing",
        ],
    )
    assert android_preflight.main() == 1
    assert "reserved .invalid hostname" in capsys.readouterr().err


@pytest.mark.parametrize(
    "url",
    [
        "http://release.invalid",
        "https://user:password@release.invalid",
        "https://release.invalid?secret=value",
        "https://release.invalid#fragment",
    ],
)
def test_android_preflight_rejects_unsafe_urls(
    monkeypatch,
    capsys,
    url: str,
) -> None:
    _clear_android_environment(monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        ["android_release_preflight.py", "--backend-url", url],
    )
    assert android_preflight.main() == 1
    assert "valid host" in capsys.readouterr().err


@pytest.mark.parametrize(
    "url",
    [
        "http://service.example",
        "https://user:password@service.example",
        "https://service.example?secret=value",
        "https://service.example#fragment",
    ],
)
def test_remote_smoke_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(remote_smoke.SmokeFailure, match="explicit HTTPS"):
        remote_smoke._validate_target(url)


def _usage_result(daily: int, monthly: int) -> remote_smoke.Result:
    return remote_smoke.Result(
        200,
        {
            "dailyUsed": daily,
            "dailyLimit": 50,
            "monthlyUsed": monthly,
            "monthlyLimit": 500,
        },
    )


def _reply_body(
    request_body: dict,
    *,
    provider: str = "deepseek",
    model: str = remote_smoke.FLASH_MODEL,
    degraded: bool = False,
) -> dict:
    return {
        "requestId": request_body["requestId"],
        "recognizedText": request_body["recognizedText"],
        "aiReply": "synthetic reply that must not be printed",
        "responseMode": "execution",
        "recognitionSource": request_body["recognitionSource"],
        "safetyLevel": "normal",
        "shouldAsk": False,
        "promptVersion": "persona-v1",
        "provider": provider,
        "model": model,
        "degraded": degraded,
    }


def test_remote_mutating_smoke_verifies_contract_and_usage_without_leaks(
    monkeypatch,
    capsys,
) -> None:
    token = "T" * 64
    usages = iter(
        [
            _usage_result(0, 0),
            _usage_result(1, 1),
            _usage_result(1, 1),
            _usage_result(1, 1),
            _usage_result(2, 2),
        ]
    )

    def fake_request(
        base_url,
        method,
        path,
        *,
        timeout,
        token=None,
        body=None,
    ):
        if path == "/healthz":
            return remote_smoke.Result(200, {"status": "ok"})
        if path == "/readyz":
            return remote_smoke.Result(200, {"status": "ready"})
        if path == "/api/profile" and token is None:
            return remote_smoke.Result(
                401,
                {
                    "detail": {
                        "code": "missing_access_token",
                        "message": "missing",
                    }
                },
            )
        if path == "/api/auth/device/register":
            return remote_smoke.Result(200, {"accessToken": token_value})
        if path == "/api/profile" and method == "GET":
            return remote_smoke.Result(
                200,
                {"assistantName": "墨灵", "updatedAt": "2026-07-27T00:00:00Z"},
            )
        if path == "/api/profile" and method == "PATCH":
            return remote_smoke.Result(
                200,
                {
                    "assistantName": body["assistantName"],
                    "updatedAt": "2026-07-27T00:00:00Z",
                },
            )
        if path == "/api/usage":
            return next(usages)
        if path == "/api/notebook/reply":
            if body["recognizedText"] == "不同载荷必须触发幂等冲突。":
                return remote_smoke.Result(
                    409,
                    {
                        "detail": {
                            "code": "idempotency_conflict",
                            "message": "conflict",
                        }
                    },
                )
            if body["deepMode"]:
                return remote_smoke.Result(
                    200,
                    _reply_body(body, model=remote_smoke.PRO_MODEL),
                )
            return remote_smoke.Result(200, _reply_body(body))
        raise AssertionError(f"unexpected request: {method} {path}")

    token_value = token
    monkeypatch.setattr(remote_smoke, "_request", fake_request)
    remote_smoke.run("https://service.example", timeout=1, exercise_api=True)
    output = capsys.readouterr().out
    assert token not in output
    assert "synthetic reply that must not be printed" not in output
    with pytest.raises(StopIteration):
        next(usages)


def test_remote_reply_contract_rejects_non_deepseek_provider() -> None:
    request = {
        "requestId": "request-123",
        "recognizedText": "synthetic",
        "recognitionSource": "test",
    }
    result = remote_smoke.Result(
        200,
        _reply_body(request, provider="fake"),
    )
    with pytest.raises(remote_smoke.SmokeFailure, match="provider must be deepseek"):
        remote_smoke._validate_reply_contract(
            "normal reply",
            result,
            request_id=request["requestId"],
            deep_mode=False,
        )


def test_remote_deep_reply_contract_accepts_explicit_flash_degradation() -> None:
    request = {
        "requestId": "request-123",
        "recognizedText": "synthetic",
        "recognitionSource": "test",
    }
    remote_smoke._validate_reply_contract(
        "deep reply",
        remote_smoke.Result(
            200,
            _reply_body(
                request,
                model=remote_smoke.FLASH_MODEL,
                degraded=True,
            ),
        ),
        request_id=request["requestId"],
        deep_mode=True,
    )


@pytest.mark.parametrize(
    ("deep_mode", "model", "degraded"),
    [
        (False, remote_smoke.PRO_MODEL, False),
        (False, remote_smoke.FLASH_MODEL, True),
        (True, remote_smoke.FLASH_MODEL, False),
        (True, remote_smoke.PRO_MODEL, True),
    ],
)
def test_remote_reply_contract_rejects_invalid_model_degradation_combinations(
    deep_mode: bool,
    model: str,
    degraded: bool,
) -> None:
    request = {
        "requestId": "request-123",
        "recognizedText": "synthetic",
        "recognitionSource": "test",
    }
    result = remote_smoke.Result(
        200,
        _reply_body(request, model=model, degraded=degraded),
    )
    with pytest.raises(remote_smoke.SmokeFailure):
        remote_smoke._validate_reply_contract(
            "reply",
            result,
            request_id=request["requestId"],
            deep_mode=deep_mode,
        )


def test_remote_reply_contract_rejects_request_id_or_core_field_mismatch() -> None:
    request = {
        "requestId": "request-123",
        "recognizedText": "synthetic",
        "recognitionSource": "test",
    }
    wrong_id = remote_smoke.Result(
        200,
        _reply_body({**request, "requestId": "request-other"}),
    )
    with pytest.raises(remote_smoke.SmokeFailure, match="requestId"):
        remote_smoke._validate_reply_contract(
            "reply",
            wrong_id,
            request_id=request["requestId"],
            deep_mode=False,
        )

    missing_reply_body = _reply_body(request)
    missing_reply_body["aiReply"] = ""
    with pytest.raises(remote_smoke.SmokeFailure, match="aiReply"):
        remote_smoke._validate_reply_contract(
            "reply",
            remote_smoke.Result(200, missing_reply_body),
            request_id=request["requestId"],
            deep_mode=False,
        )


def test_remote_usage_contract_detects_duplicate_charge_or_missing_charge() -> None:
    baseline = remote_smoke.UsageSnapshot(daily_used=0, monthly_used=0)
    unchanged = remote_smoke.UsageSnapshot(daily_used=0, monthly_used=0)
    charged_twice = remote_smoke.UsageSnapshot(daily_used=2, monthly_used=2)
    with pytest.raises(remote_smoke.SmokeFailure, match="change by 1"):
        remote_smoke._expect_usage_delta(
            "normal reply",
            unchanged,
            baseline,
            1,
        )
    with pytest.raises(remote_smoke.SmokeFailure, match="change by 0"):
        remote_smoke._expect_usage_delta(
            "idempotent replay",
            charged_twice,
            baseline,
            0,
        )
