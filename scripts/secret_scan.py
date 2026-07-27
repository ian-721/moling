from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PATHS = (
    re.compile(r"(^|/)\.env($|\.)", re.IGNORECASE),
    re.compile(r"\.(jks|keystore|p12|pem|key)$", re.IGNORECASE),
    re.compile(r"\.(apk|aab|db|sqlite|sqlite3|log)$", re.IGNORECASE),
    re.compile(r"(^|/)(private_seed|private_memory)(/|$)", re.IGNORECASE),
)
ALLOW_PATHS = {"backend/.env.example"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def tracked_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return [
        path.decode("utf-8", errors="surrogateescape")
        for path in output.split(b"\0")
        if path
    ]


def main() -> int:
    failures: list[str] = []
    for relative in tracked_files():
        normalized = relative.replace("\\", "/")
        if normalized not in ALLOW_PATHS and any(
            pattern.search(normalized) for pattern in BLOCKED_PATHS
        ):
            failures.append(f"blocked sensitive path: {normalized}")
            continue

        path = ROOT / relative
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                failures.append(f"secret-like content: {normalized}")
                break

    if failures:
        print("\n".join(failures))
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
