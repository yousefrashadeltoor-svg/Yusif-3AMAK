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
  PID="$(adb shell pidof app.dayflow.android 2>/dev/null | tr -d '\\r' || true)"
  if [[ -n "$PID" ]]; then break; fi
  sleep 1
done
if [[ -z "$PID" ]]; then
  adb logcat -d -s AndroidRuntime:E
  echo "DAYFLOW native process failed to start" >&2
  exit 1
fi
sleep 5
adb shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' | grep -F 'app.dayflow.android/.MainActivity'
if adb logcat -d -s AndroidRuntime:E | grep -B2 -A8 -F 'Process: app.dayflow.android'; then
  echo "DAYFLOW native app crashed after launch" >&2
  exit 1
fi
echo "Native DAYFLOW Compose activity cold-launched successfully (PID=$PID)."
gradle --no-daemon -p "$GITHUB_WORKSPACE/native-dayflow" :app:connectedDebugAndroidTest
