# Moling v0.8 signed-device acceptance record

> 这是空白证据模板，不是已通过声明。每台设备单独复制一份到仓库外的
> 受控证据目录。不得记录 Bearer Token、keystore 密码、笔记正文、最近
> 上下文、完整回复、设备个人账号或未脱敏 serial。

## 1. Build provenance

| Field | Recorded value |
|---|---|
| Acceptance date/time/timezone | |
| Tester | |
| Git commit | |
| Branch/PR | |
| Release hostname (no credentials) | |
| APK filename | |
| APK SHA-256 | |
| Signing certificate SHA-256 | |
| AAB SHA-256 | |
| `android_release_preflight.py --require-signing` evidence path | |
| Gradle build log evidence path | |

Recommended read-only evidence commands:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '<signed-apk>'
Get-FileHash -Algorithm SHA256 -LiteralPath '<release-aab>'
apksigner verify --verbose --print-certs '<signed-apk>'
```

## 2. Device and recognition environment

| Field | Recorded value |
|---|---|
| Manufacturer/model | |
| Android/HarmonyOS version | |
| Build number/security patch | |
| GMS present | yes / no / unknown |
| Google Play Services version | |
| Stylus model/input method | |
| Network type | |
| ML Kit model initially present | yes / no / unknown |
| ML Kit download allowed | yes / no |
| Device serial evidence | redacted |

## 3. Install and configuration evidence

```powershell
adb devices
adb install -r '<signed-apk>'
adb shell dumpsys package com.moling.livingnotebook
```

| Check | Expected | Result | Timestamp | Evidence path |
|---|---|---|---|---|
| APK signature verifies | permanent expected certificate | | | |
| Clean install/upgrade succeeds | `Success` | | | |
| Package/version | `com.moling.livingnotebook`, `0.8.0` / `800` | | | |
| Release backend | authorized HTTPS target | | | |
| Cleartext | rejected/disabled | | | |
| Vision fallback | disabled | | | |

## 4. Functional and recovery matrix

Use synthetic, non-private handwriting. Screenshots and screen recordings must not contain
personal notes, Token, notifications or account identifiers.

| Check | Procedure | Expected | Result | Evidence path |
|---|---|---|---|---|
| New device registration | first launch on clean app data | profile loads; no Token shown | | |
| Token persistence | close/relaunch without clearing data | same principal/profile remains | | |
| Profile rename | set a synthetic role name | only current principal changes | | |
| Usage read | open/use the relevant flow | bounded usage loads | | |
| Normal DeepSeek reply | synthetic handwriting, normal mode | ink reply appears | | |
| Deep reply | explicit deep mode | deep reply appears; no fallback claim | | |
| Local handwriting | write with stylus | stroke is saved immediately | | |
| ML Kit recognition | recognize synthetic Han text | actual result recorded as pass/fail | | |
| Offline preservation | disable network before response | strokes remain editable/recoverable | | |
| Force-stop recovery | force-stop during `SENDING`, relaunch | turn becomes safely retryable | | |
| Same request ID retry | retry recovered outbox item | no duplicate provider result/charge | | |
| Absorption write barrier | add new stroke during absorption | new stroke remains | | |
| Process restart after success | restart after reply stored | reply/turn remains | | |
| Invalid/expired session | exercise authorized test session only | cached name cleared; safe re-registration | | |

Suggested force-stop command:

```powershell
adb shell am force-stop com.moling.livingnotebook
```

## 5. Huawei no-GMS gate

| Check | Expected | Result | Evidence path |
|---|---|---|---|
| GMS state independently confirmed | yes/no, not inferred from brand | | |
| ML Kit model availability check | explicit state | | |
| First model download | success or reproducible failure category | | |
| Recognition after download/relaunch | actual synthetic input result | | |
| Failure UX | clear failure; strokes retained | | |
| Vision fallback | remains disabled | | |

If ML Kit cannot work on the target Huawei device, record `FAIL` with device/system/model
evidence. Do not mark the gate passed and do not enable Vision to hide the failure.

## 6. Log and privacy evidence

| Check | Expected | Result | Evidence path |
|---|---|---|---|
| App logs | no note/context/full reply/Token | | |
| Backend logs | no Authorization/Token hash/content | | |
| Screenshots/video | synthetic content only | | |
| Crash/debug artifacts | no private payload/image | | |

## 7. Final device verdict

- Verdict: `PASS` / `FAIL` / `BLOCKED`
- Blocking check IDs:
- Reproduction steps:
- Recoverability/data-loss result:
- Evidence directory:
- Reviewer/date:

`BLOCKED` is required when hardware, network, account, model download or authorization was
not actually available. An APK build alone is never a device pass.
