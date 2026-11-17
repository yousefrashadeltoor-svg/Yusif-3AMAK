#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
test -s "$APK"

adb install -r "$APK"
adb shell pm grant app.dayflow.android android.permission.POST_NOTIFICATIONS || true
adb shell am force-stop app.dayflow.android
adb logcat -c
adb shell monkey -p app.dayflow.android -c android.intent.category.LAUNCHER 1

PID=""
for attempt in $(seq 1 30); do
  PID="$(adb shell pidof app.dayflow.android 2>/dev/null | tr -d '\r' || true)"
  if [[ -n "$PID" ]]; then break; fi
  sleep 1
done

if [[ -z "$PID" ]]; then
  adb logcat -d -s AndroidRuntime:E
  echo "DAYFLOW native process failed to start" >&2
  exit 1
fi

sleep 5
ACTIVITY_STATE="$(adb shell dumpsys activity activities 2>&1 || true)"
RESUMED_ACTIVITY="$(printf '%s\n' "$ACTIVITY_STATE" | grep -E 'mResumedActivity|topResumedActivity' | grep -F 'app.dayflow.android' || true)"
if [[ -z "$RESUMED_ACTIVITY" ]]; then
  printf '%s\n' "$ACTIVITY_STATE" | tail -n 100 >&2
  echo "DAYFLOW package process started but its activity was not reported as resumed." >&2
  exit 1
fi

CRASH_LOG="$(adb logcat -d -s AndroidRuntime:E 2>/dev/null || true)"
if printf '%s\n' "$CRASH_LOG" | grep -B2 -A8 -F 'Process: app.dayflow.android'; then
  echo "DAYFLOW native app crashed after launch" >&2
  exit 1
fi

echo "Native DAYFLOW Compose activity cold-launched successfully (PID=$PID)."
gradle --no-daemon --stacktrace -p "$GITHUB_WORKSPACE/native-dayflow" :app:connectedDebugAndroidTest
