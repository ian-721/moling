from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


@dataclass(frozen=True)
class Result:
    status: int
    body: dict[str, Any]


@dataclass(frozen=True)
class UsageSnapshot:
    daily_used: int
    monthly_used: int


class SmokeFailure(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(_NoRedirect)
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"
REPLY_MODES = {
    "companion",
    "mirror",
    "judgment",
    "root_cause",
    "decision",
    "execution",
    "grounding",
    "challenge",
    "quiet",
    "safety",
}
SAFETY_LEVELS = {"normal", "elevated", "critical"}


def _safe_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SmokeFailure("response was not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise SmokeFailure("response JSON was not an object")
    return value


def _request(
    base_url: str,
    method: str,
    path: str,
    *,
    timeout: float,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> Result:
    headers = {
        "Accept": "application/json",
        "User-Agent": "moling-m0b3a-smoke/1",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return Result(response.status, _safe_json(response.read()))
    except HTTPError as error:
        body = {} if 300 <= error.code < 400 else _safe_json(error.read())
        return Result(error.code, body)
    except (TimeoutError, URLError, OSError) as error:
        raise SmokeFailure(f"network request failed: {type(error).__name__}") from error


def _error_code(result: Result) -> str | None:
    detail = result.body.get("detail")
    if isinstance(detail, dict):
        code = detail.get("code")
        return code if isinstance(code, str) else None
    return None


def _expect(
    label: str,
    result: Result,
    status: int,
    *,
    code: str | None = None,
) -> None:
    if result.status != status:
        raise SmokeFailure(
            f"{label}: expected HTTP {status}, received HTTP {result.status}"
        )
    if code is not None and _error_code(result) != code:
        raise SmokeFailure(f"{label}: expected safe error code {code}")
    print(f"PASS {label}")


def _validate_target(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SmokeFailure(
            "base URL must be explicit HTTPS with a valid host and no credentials, query, or fragment"
        )
    return normalized


def _usage_snapshot(label: str, result: Result) -> UsageSnapshot:
    _expect(f"{label} HTTP", result, 200)
    integer_fields = (
        "dailyUsed",
        "dailyLimit",
        "monthlyUsed",
        "monthlyLimit",
    )
    for field in integer_fields:
        value = result.body.get(field)
        if type(value) is not int:
            raise SmokeFailure(f"{label}: {field} must be an integer")
        if value < 0:
            raise SmokeFailure(f"{label}: {field} must not be negative")
    if result.body["dailyLimit"] <= 0 or result.body["monthlyLimit"] <= 0:
        raise SmokeFailure(f"{label}: usage limits must be positive")
    print(f"PASS {label} response contract")
    return UsageSnapshot(
        daily_used=result.body["dailyUsed"],
        monthly_used=result.body["monthlyUsed"],
    )


def _expect_usage_delta(
    label: str,
    current: UsageSnapshot,
    baseline: UsageSnapshot,
    expected_delta: int,
) -> None:
    if (
        current.daily_used != baseline.daily_used + expected_delta
        or current.monthly_used != baseline.monthly_used + expected_delta
    ):
        raise SmokeFailure(
            f"{label}: daily/monthly usage did not change by {expected_delta}"
        )
    print(f"PASS {label}")


def _require_nonempty_string(
    label: str,
    body: dict[str, Any],
    field: str,
) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SmokeFailure(f"{label}: {field} must be a non-empty string")
    return value


def _validate_reply_contract(
    label: str,
    result: Result,
    *,
    request_id: str,
    deep_mode: bool,
) -> None:
    _expect(f"{label} HTTP", result, 200)
    body = result.body
    returned_request_id = _require_nonempty_string(label, body, "requestId")
    if returned_request_id != request_id:
        raise SmokeFailure(f"{label}: response requestId did not match the request")
    _require_nonempty_string(label, body, "recognizedText")
    _require_nonempty_string(label, body, "aiReply")
    _require_nonempty_string(label, body, "recognitionSource")
    _require_nonempty_string(label, body, "promptVersion")

    response_mode = body.get("responseMode")
    if response_mode not in REPLY_MODES:
        raise SmokeFailure(f"{label}: responseMode was outside the contract")
    safety_level = body.get("safetyLevel")
    if safety_level not in SAFETY_LEVELS:
        raise SmokeFailure(f"{label}: safetyLevel was outside the contract")
    if type(body.get("shouldAsk")) is not bool:
        raise SmokeFailure(f"{label}: shouldAsk must be a boolean")
    if body.get("provider") != "deepseek":
        raise SmokeFailure(f"{label}: provider must be deepseek")
    if type(body.get("degraded")) is not bool:
        raise SmokeFailure(f"{label}: degraded must be a boolean")

    model = body.get("model")
    degraded = body["degraded"]
    if not deep_mode:
        if model != FLASH_MODEL or degraded:
            raise SmokeFailure(
                f"{label}: normal reply must use {FLASH_MODEL} without degradation"
            )
    elif degraded:
        if model != FLASH_MODEL:
            raise SmokeFailure(
                f"{label}: degraded deep reply must fall back to {FLASH_MODEL}"
            )
    elif model != PRO_MODEL:
        raise SmokeFailure(
            f"{label}: non-degraded deep reply must use {PRO_MODEL}"
        )
    print(f"PASS {label} DeepSeek response contract")


def run(base_url: str, timeout: float, exercise_api: bool) -> None:
    health = _request(base_url, "GET", "/healthz", timeout=timeout)
    _expect("HTTPS /healthz", health, 200)
    if health.body.get("status") != "ok":
        raise SmokeFailure("/healthz did not report ok")

    ready = _request(base_url, "GET", "/readyz", timeout=timeout)
    _expect("database-backed /readyz", ready, 200)
    if ready.body.get("status") != "ready":
        raise SmokeFailure("/readyz did not report ready")

    unauthorized = _request(base_url, "GET", "/api/profile", timeout=timeout)
    _expect(
        "unauthenticated profile rejection",
        unauthorized,
        401,
        code="missing_access_token",
    )

    if not exercise_api:
        print("PASS probe-only smoke completed; no principal or model call was created")
        return

    installation_id = str(uuid4())
    registration = _request(
        base_url,
        "POST",
        "/api/auth/device/register",
        timeout=timeout,
        body={"installationId": installation_id},
    )
    _expect("new device registration", registration, 200)
    token = registration.body.get("accessToken")
    if not isinstance(token, str) or len(token) < 32:
        raise SmokeFailure("registration did not return an opaque access token")

    profile = _request(
        base_url, "GET", "/api/profile", timeout=timeout, token=token
    )
    _expect("Bearer token reuse for profile", profile, 200)

    acceptance_name = f"墨灵验收{uuid4().hex[:6]}"
    renamed = _request(
        base_url,
        "PATCH",
        "/api/profile",
        timeout=timeout,
        token=token,
        body={"assistantName": acceptance_name},
    )
    _expect("principal-scoped profile rename", renamed, 200)
    if renamed.body.get("assistantName") != acceptance_name:
        raise SmokeFailure("profile rename was not persisted")

    initial_usage = _usage_snapshot(
        "initial principal usage",
        _request(
            base_url, "GET", "/api/usage", timeout=timeout, token=token
        ),
    )

    request_id = f"smoke-{uuid4()}"
    normal_payload = {
        "requestId": request_id,
        "pageId": f"smoke-page-{uuid4()}",
        "recognizedText": "远程验收占位文本：请只给出一句简短回应。",
        "recognitionSource": "m0b3a-smoke",
        "recentContext": "",
        "deepMode": False,
    }
    normal = _request(
        base_url,
        "POST",
        "/api/notebook/reply",
        timeout=timeout,
        token=token,
        body=normal_payload,
    )
    _validate_reply_contract(
        "normal reply",
        normal,
        request_id=request_id,
        deep_mode=False,
    )
    usage_after_normal = _usage_snapshot(
        "usage after normal reply",
        _request(
            base_url, "GET", "/api/usage", timeout=timeout, token=token
        ),
    )
    _expect_usage_delta(
        "normal reply charged exactly one request",
        usage_after_normal,
        initial_usage,
        1,
    )

    replay = _request(
        base_url,
        "POST",
        "/api/notebook/reply",
        timeout=timeout,
        token=token,
        body=normal_payload,
    )
    _validate_reply_contract(
        "same requestId idempotent replay",
        replay,
        request_id=request_id,
        deep_mode=False,
    )
    if replay.body != normal.body:
        raise SmokeFailure("idempotent replay did not return the stored response")
    usage_after_replay = _usage_snapshot(
        "usage after idempotent replay",
        _request(
            base_url, "GET", "/api/usage", timeout=timeout, token=token
        ),
    )
    _expect_usage_delta(
        "idempotent replay did not consume usage",
        usage_after_replay,
        usage_after_normal,
        0,
    )

    conflict_payload = dict(normal_payload)
    conflict_payload["recognizedText"] = "不同载荷必须触发幂等冲突。"
    conflict = _request(
        base_url,
        "POST",
        "/api/notebook/reply",
        timeout=timeout,
        token=token,
        body=conflict_payload,
    )
    _expect(
        "different payload idempotency conflict",
        conflict,
        409,
        code="idempotency_conflict",
    )
    usage_after_conflict = _usage_snapshot(
        "usage after idempotency conflict",
        _request(
            base_url, "GET", "/api/usage", timeout=timeout, token=token
        ),
    )
    _expect_usage_delta(
        "idempotency conflict did not consume usage",
        usage_after_conflict,
        usage_after_replay,
        0,
    )

    deep_payload = dict(normal_payload)
    deep_payload.update(
        requestId=f"smoke-deep-{uuid4()}",
        recognizedText="远程深度回应验收占位文本：请给出一个简短判断。",
        deepMode=True,
    )
    deep = _request(
        base_url,
        "POST",
        "/api/notebook/reply",
        timeout=timeout,
        token=token,
        body=deep_payload,
    )
    _validate_reply_contract(
        "deep reply",
        deep,
        request_id=deep_payload["requestId"],
        deep_mode=True,
    )
    usage_after_deep = _usage_snapshot(
        "usage after deep reply",
        _request(
            base_url, "GET", "/api/usage", timeout=timeout, token=token
        ),
    )
    _expect_usage_delta(
        "deep reply charged exactly one request",
        usage_after_deep,
        usage_after_conflict,
        1,
    )
    print("PASS mutating smoke completed; token and response content were suppressed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe an explicitly supplied Moling HTTPS deployment. By default "
            "only health/readiness and an unauthenticated 401 are checked."
        )
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--exercise-api",
        action="store_true",
        help=(
            "Explicitly create a disposable device principal and make normal/deep "
            "provider calls, including idempotency checks."
        ),
    )
    args = parser.parse_args()
    try:
        base_url = _validate_target(args.base_url)
        if args.timeout <= 0:
            raise SmokeFailure("timeout must be positive")
        run(base_url, args.timeout, args.exercise_api)
    except SmokeFailure as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
