from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
APP_GRADLE = ROOT / "moling-android" / "app" / "build.gradle.kts"
MANIFEST = (
    ROOT
    / "moling-android"
    / "app"
    / "src"
    / "main"
    / "AndroidManifest.xml"
)
SIGNING_VARIABLES = (
    "MOLING_KEYSTORE_PATH",
    "MOLING_KEYSTORE_PASSWORD",
    "MOLING_KEY_ALIAS",
    "MOLING_KEY_PASSWORD",
)


def _valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme.lower() == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _source_guard_failures() -> list[str]:
    gradle = APP_GRADLE.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")
    expected_gradle = (
        'buildConfigField("Boolean", "ENABLE_VISION_FALLBACK", "false")',
        'manifestPlaceholders["usesCleartextTraffic"] = "false"',
        "https://release.invalid",
        "A signed Release requires an explicit MOLING_RELEASE_BACKEND_URL",
        *SIGNING_VARIABLES,
    )
    failures = [
        f"Android Gradle source guard missing: {snippet}"
        for snippet in expected_gradle
        if snippet not in gradle
    ]
    if 'android:usesCleartextTraffic="${usesCleartextTraffic}"' not in manifest:
        failures.append("Android manifest is not controlled by the cleartext placeholder")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Moling Release URL, cleartext/Vision source guards, and "
            "all-or-none signing inputs without printing secret values."
        )
    )
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("MOLING_RELEASE_BACKEND_URL"),
        help="Explicit Release HTTPS base URL; may also come from the matching environment variable.",
    )
    parser.add_argument(
        "--require-signing",
        action="store_true",
        help="Fail unless all four permanent signing variables are present.",
    )
    args = parser.parse_args()

    failures = _source_guard_failures()
    if not args.backend_url:
        failures.append(
            "MOLING_RELEASE_BACKEND_URL or --backend-url is required"
        )
    elif not _valid_https_url(args.backend_url):
        failures.append(
            "Release backend URL must be HTTPS with a valid host and no credentials, query, or fragment"
        )
    elif args.require_signing and urlparse(args.backend_url).hostname.endswith(
        ".invalid"
    ):
        failures.append("A signed Release cannot use the reserved .invalid hostname")

    signing_present = {
        name: bool(os.environ.get(name, "").strip()) for name in SIGNING_VARIABLES
    }
    present_count = sum(signing_present.values())
    if present_count not in {0, len(SIGNING_VARIABLES)}:
        failures.append(
            "Release signing is partial; set all four MOLING_KEYSTORE_* variables or none"
        )
    elif present_count == 0 and args.require_signing:
        failures.append("Permanent Release signing variables are required")
    elif present_count == len(SIGNING_VARIABLES):
        keystore_path = Path(os.environ["MOLING_KEYSTORE_PATH"])
        if not keystore_path.is_file():
            failures.append("Configured Release keystore file is not readable")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print("PASS Release backend URL is structurally valid HTTPS")
    print("PASS Release cleartext traffic source guard is disabled")
    print("PASS Release Vision fallback source guard is disabled")
    if present_count == 0:
        print("PASS signing inputs are all absent (unsigned build baseline only)")
    else:
        print("PASS all permanent signing inputs are present (values suppressed)")
        print("PASS configured keystore file is readable (path suppressed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
