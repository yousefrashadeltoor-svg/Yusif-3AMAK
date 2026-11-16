#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path argument is required}"
if [[ ! -s "$APK" ]]; then
  echo "::error::Verified APK is missing: $APK" >&2
  exit 1
fi

adb install -r "$APK"
adb shell pm path app.dayflow.android | grep -q '^package:'
adb logcat -c
adb shell pm grant app.dayflow.android android.permission.POST_NOTIFICATIONS || true
adb shell am force-stop app.dayflow.android
adb shell monkey -p app.dayflow.android -c android.intent.category.LAUNCHER 1

PID=""
for attempt in $(seq 1 30); do
  PID="$(adb shell pidof app.dayflow.android 2>/dev/null | tr -d '\r' || true)"
  if [[ -n "$PID" ]]; then break; fi
  sleep 1
done
if [[ -z "$PID" ]]; then
  echo "::error::DAYFLOW process did not start after launch." >&2
  adb logcat -d -s AndroidRuntime:E
  exit 1
fi

sleep 8
adb shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' | grep -F 'app.dayflow.android'
if adb logcat -d -s AndroidRuntime:E | grep -B2 -A8 -F 'Process: app.dayflow.android'; then
  echo "::error::DAYFLOW crashed during emulator cold launch." >&2
  exit 1
fi

echo "DAYFLOW installed and cold-launched successfully on Android API 35 (PID=$PID)."
