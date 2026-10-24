# Moling (墨灵) — Living Notebook

**An AI notebook that replies in ink, right where you write.**

[English](README.md) · [简体中文](README.zh-CN.md)

Moling is an **Android-tablet-first, handwriting-native AI notebook**. Write directly on the page; the app saves your pen strokes locally and recognizes handwriting on the device. A backend prepares a reply, and the answer appears as ink on the same page.

This is not a chat app in notebook clothing. The interaction is built around paper, handwriting, and an animated ink response—not chat bubbles, avatars, or a message list.

> **Project status — v0.8 / M0-B engineering baseline.** This repository contains Android and backend implementation, tests, release-build configuration, and deployment preflight tools. It does **not** by itself establish a live production deployment, permanently signed release, app-store submission, or successful testing on a physical device.

## What is implemented

| Area | Code in this repository |
| --- | --- |
| **Handwriting-first Android UI** | Kotlin/Jetpack Compose canvas, ML Kit Digital Ink Recognition, and an ink-reply overlay |
| **Local recovery** | Room stores pages, complete stroke points, notebook turns, and the reply outbox; failures and restarts are designed not to discard the original writing |
| **Device-based access** | Anonymous device registration; 256-bit opaque bearer tokens with server-side HMAC storage and Android Keystore AES-256-GCM protection |
| **Identity isolation** | The assistant's display name is scoped to the authenticated principal; sharing a name does not share an identity or memory |
| **Backend** | Python/FastAPI, SQLAlchemy 2.x, Alembic, SQLite for development/tests and PostgreSQL for production configuration |
| **Request and cost controls** | Per-principal rate limits and quotas, global CNY budget reservation, request idempotency, fingerprint conflicts, and recovery leases |
| **Build and deployment tools** | Docker, migration/health checks, Android Debug and Release build paths, APK/AAB configuration, and release preflight scripts |

The model provider is configurable: local development uses a fake provider, while the production configuration targets **DeepSeek V4**. The code's presence is not evidence of an operating hosted service.

## How a reply moves through the system

~~~text
User finishes a pen stroke
  → The stroke is persisted in Room
  → "Reply" snapshots the selected stroke IDs and request ID
  → ML Kit recognizes handwriting on-device
  → Android attaches the device's bearer token
  → Backend checks identity, quotas, budget, and idempotency
  → DeepSeek V4 (or a fake test provider) generates a response
  → The reply is stored locally before being shown
  → InkReplyOverlay renders the response as ink
  → Only the snapshotted strokes are absorbed
~~~

If recognition, the network, or the model fails, the original strokes remain recoverable. New strokes written while a response is appearing are not part of the earlier request snapshot.

## Explore the project locally

### Backend

Use **Python 3.12+**. The provided development environment uses SQLite and the fake provider; **no DeepSeek API key is needed**.

~~~powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest -q
python -m uvicorn main:app --host 127.0.0.1 --port 8000
~~~

Selected routes:

| Route | Purpose |
| --- | --- |
| `GET /healthz`, `GET /readyz` | Health and readiness |
| `POST /api/auth/device/register` | Anonymous device registration |
| `GET /api/profile`, `PATCH /api/profile` | Per-device assistant profile |
| `GET /api/usage` | Usage |
| `POST /api/notebook/reply` | Generate a notebook reply |

Except for registration and health/readiness, these APIs require an authenticated bearer token. See the [remote-install and recovery protocol](docs/launch/M0B_REMOTE_INSTALL_PROTOCOL.md) for the exact request and state contracts.

### Android

Use **JDK 21** and the checked-in Gradle wrapper:

~~~powershell
cd moling-android
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug `
  :app:assembleDebug :app:assembleRelease :app:bundleRelease
~~~

The baseline declares `versionCode=800` and `versionName=0.8.0`. CI can produce **unsigned** Release artifacts; a permanently signed release needs an authorized signing key and an explicit HTTPS backend URL. No real signing keys are shipped here.

Read the [build, signing, and device-install guide](docs/release/V0_8_BUILD_SIGN_INSTALL.md) before interpreting build artifacts as an actual release or device acceptance result.

## Verification and deployment boundaries

From the repository root, the source-level secret scan can be run with:

~~~powershell
python scripts/secret_scan.py
~~~

The GitHub Actions workflow is configured for backend tests, migration checks (including a PostgreSQL 17 service), negative production-config checks, the secret scan, a Docker build, and Android unit tests/lint/build tasks. Configured checks do not replace results from a real device or a live environment.

Production configuration requires PostgreSQL, HTTPS, a DeepSeek API key supplied through a secret manager, signing material for signed Android artifacts, and explicit authentication/quota/budget settings. Known placeholder secrets are rejected. Do not commit production values.

- [Backend deployment](docs/deployment/M0B_DEPLOYMENT.md)
- [Real-environment preflight and remaining acceptance work](docs/deployment/M0B3A_REAL_ENVIRONMENT_PREFLIGHT.md)
- [Identity and naming boundaries](docs/launch/00_IDENTITY_AND_NAMING_BOUNDARY.md)

### Not yet established by this baseline

Cloud notebook sync and cross-device memory; Google/Huawei/email login; importing a private long-term memory seed; subscriptions, payments, and store entitlements; iOS or web clients; formal store submissions and production rollout.

## About the project

Moling explores a simple interaction question: **What would an AI assistant feel like if the notebook—not the chat window—were the interface?** The repository documents the engineering work toward that experience, including recovery and identity boundaries, without treating a code or CI result as proof that the product has shipped.

**Maintainer:** [Yanyang (Ian) Zhao](https://github.com/ian-721).

**Source availability:** The repository is publicly viewable. No repository-wide open-source license is included here at present; bundled third-party assets may have their own terms.
