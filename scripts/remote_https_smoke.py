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


class SmokeFailure(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(_NoRedirect)


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

    usage = _request(
        base_url, "GET", "/api/usage", timeout=timeout, token=token
    )
    _expect("principal usage read", usage, 200)

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
    _expect("real normal reply", normal, 200)

    replay = _request(
        base_url,
        "POST",
        "/api/notebook/reply",
        timeout=timeout,
        token=token,
        body=normal_payload,
    )
    _expect("same requestId idempotent replay", replay, 200)
    if replay.body != normal.body:
        raise SmokeFailure("idempotent replay did not return the stored response")

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
    _expect("real deep reply", deep, 200)
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
