# Moling v0.8 build, signing, and install

## Build

Use JDK 21 and the checked-in wrapper:

```powershell
cd moling-android
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug `
  :app:assembleDebug :app:assembleRelease :app:bundleRelease
```

`versionCode=800`, `versionName=0.8.0`, and package name
`com.moling.livingnotebook` are fixed for this baseline. Debug defaults to
`http://10.0.2.2:8000`. Release defaults to
`https://api.moling.app` and rejects non-HTTPS overrides:

```powershell
.\gradlew.bat :app:assembleRelease :app:bundleRelease `
  -PMOLING_RELEASE_BACKEND_URL=https://your-authorized-host.example
```

Vision fallback remains false in both variants; Release manifest disables
cleartext traffic.

## Permanent release signing

The repository never contains a keystore or password. Set all four variables
in the local shell or CI secret manager:

```powershell
$env:MOLING_KEYSTORE_PATH='D:\secure\moling-release.jks'
$env:MOLING_KEYSTORE_PASSWORD='<secret>'
$env:MOLING_KEY_ALIAS='<alias>'
$env:MOLING_KEY_PASSWORD='<secret>'
```

Then run `:app:assembleRelease :app:bundleRelease`. Partial configuration
fails at Gradle configuration time. With none of the variables set, CI still
builds the unsigned Release APK/AAB baseline. Do not create a temporary
permanent keystore merely to make a signed-artifact claim.

Expected untracked outputs:

- `app/build/outputs/apk/debug/app-debug.apk`
- `app/build/outputs/apk/release/app-release-unsigned.apk` when unsigned
- `app/build/outputs/bundle/release/app-release.aab`

## Install and recovery matrix

```powershell
adb devices
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

On a Huawei device record model, Android/HarmonyOS version, GMS availability,
and ML Kit Digital Ink model download state. Verify registration/token
persistence, profile rename, writing and response, offline failure, force-stop
and relaunch recovery, retry with the same request ID, and that strokes written
during absorption remain. Vision must not be enabled to hide an ML Kit failure.

If no authorized physical device is connected, APK generation is a code/build
result only; it is not a true-device pass.
