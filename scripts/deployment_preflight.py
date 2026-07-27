from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import ConfigurationError, Settings  # noqa: E402


REQUIRED_PRODUCTION_VARIABLES = (
    "MOLING_ENV",
    "MODEL_PROVIDER",
    "DATABASE_URL",
    "DEEPSEEK_API_KEY",
    "PROVIDER_USER_ID_SALT",
    "TOKEN_HASH_PEPPER",
    "ACCESS_TOKEN_TTL_SECONDS",
    "REGISTRATION_ENABLED",
    "REGISTRATION_REQUESTS_PER_MINUTE",
    "REGISTRATION_MAX_PRINCIPALS",
    "PRINCIPAL_REQUESTS_PER_MINUTE",
    "PRINCIPAL_DAILY_REQUEST_LIMIT",
    "PRINCIPAL_MONTHLY_REQUEST_LIMIT",
    "GLOBAL_MONTHLY_BUDGET_CNY",
    "REQUEST_LEASE_SECONDS",
    "REQUEST_MAX_ATTEMPTS",
    "REQUEST_COST_RESERVATION_CNY",
    "VISION_FALLBACK_ENABLED",
    "DEBUG_IMAGE_SAVE_ENABLED",
)


def main() -> int:
    missing = [
        name
        for name in REQUIRED_PRODUCTION_VARIABLES
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        print(
            "FAIL missing required production variables: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    try:
        settings = Settings.from_env()
    except (ConfigurationError, TypeError, ValueError) as error:
        print(f"FAIL unsafe production configuration: {error}", file=sys.stderr)
        return 1

    if not settings.is_production:
        print("FAIL MOLING_ENV must be production", file=sys.stderr)
        return 1

    print("PASS production environment selected")
    print("PASS DeepSeek production provider selected")
    print("PASS PostgreSQL runtime URL selected")
    print("PASS runtime secrets are present (values suppressed)")
    print("PASS authentication, quota, lease, and budget controls are explicit")
    print("PASS Vision fallback and debug image persistence are disabled")
    print("PASS deployment preflight completed without opening a network connection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
