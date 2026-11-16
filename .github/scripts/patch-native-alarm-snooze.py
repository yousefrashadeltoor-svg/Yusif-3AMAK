#!/usr/bin/env python3
"""Add persistent, real Android alarm snooze scheduling to DAYFLOW."""
from __future__ import annotations
from pathlib import Path

ROOT = Path("android/app/src/main/java/app/dayflow/android")

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if new in source:
        return
    if old not in source:
        raise SystemExit(f"{path.name}: expected source marker not found ({label}); refusing unsafe rewrite.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

# AlarmScheduler: a snooze has its own PendingIntent/request code and persistent record.
p = ROOT / "AlarmScheduler.java"
replace_once(
    p,
    '    private AlarmScheduler() {}\n',
    '    private static final String SNOOZE_ACTION_PREFIX = "app.dayflow.android.ALARM_SNOOZE.";\n    private AlarmScheduler() {}\n',
    "snooze action constant",
)
replace_once(
    p,
    '        c.getSharedPreferences("dayflow_native", 0).edit().remove("alarm_" + id).apply();',
    '        cancelSnooze(c, id);\n        c.getSharedPreferences("dayflow_native", 0).edit().remove("alarm_" + id).apply();',
    "cancel snooze with original alarm",
)
replace_once(
    p,
    '    static void reschedule(Context c, String id) {',
    '''    private static PendingIntent pendingSnooze(Context c, String id, Intent intent, int flags) {
        int request = (id.hashCode() ^ 0x40000000) & 0x7fffffff;
        Intent value = intent == null
                ? new Intent(c, AlarmReceiver.class).setAction(SNOOZE_ACTION_PREFIX + id).putExtra("id", id)
                : intent;
        return PendingIntent.getBroadcast(c, request, value, flags);
    }

    static void cancelSnooze(Context c, String id) {
        if (id == null || id.isEmpty()) return;
        PendingIntent pi = pendingSnooze(c, id, null,
                PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);
        if (pi != null) {
            AlarmManager manager = (AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
            if (manager != null) manager.cancel(pi);
            pi.cancel();
        }
        c.getSharedPreferences("dayflow_native", 0).edit().remove("snooze_" + id).apply();
    }

    static void scheduleSnooze(Context c, String id, String label, String soundUri,
                               boolean vibrate, int snoozeMinutes) throws Exception {
        if (id == null || id.isEmpty()) throw new IllegalArgumentException("Alarm ID is required for snooze");
        int minutes = Math.max(1, Math.min(60, snoozeMinutes));
        JSONObject data = new JSONObject();
        data.put("id", id);
        data.put("label", label == null ? "DAYFLOW alarm" : label);
        data.put("soundUri", soundUri == null ? "" : soundUri);
        data.put("vibrate", vibrate);
        data.put("snooze", minutes);
        data.put("triggerAt", System.currentTimeMillis() + minutes * 60_000L);
        try {
            scheduleSnoozeData(c, data);
        } catch (Exception error) {
            c.getSharedPreferences("dayflow_native", 0).edit().remove("snooze_" + id).apply();
            throw error;
        }
    }

    private static void scheduleSnoozeData(Context c, JSONObject data) throws Exception {
        String id = data.getString("id");
        long triggerAt = data.optLong("triggerAt", 0L);
        if (triggerAt <= 0L) throw new IllegalArgumentException("Snooze trigger time is invalid");
        if (triggerAt <= System.currentTimeMillis()) {
            triggerAt = System.currentTimeMillis() + 30_000L;
            data.put("triggerAt", triggerAt);
        }
        Intent intent = new Intent(c, AlarmReceiver.class)
                .setAction(SNOOZE_ACTION_PREFIX + id)
                .putExtra("id", id)
                .putExtra("label", data.optString("label", "DAYFLOW alarm"))
                .putExtra("soundUri", data.optString("soundUri", ""))
                .putExtra("vibrate", data.optBoolean("vibrate", true))
                .putExtra("snooze", data.optInt("snooze", 10));
        PendingIntent pi = pendingSnooze(c, id, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        AlarmManager manager = (AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
        if (manager == null) throw new IllegalStateException("Android AlarmManager is unavailable");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && manager.canScheduleExactAlarms()) {
            manager.setAlarmClock(new AlarmManager.AlarmClockInfo(triggerAt, pi), pi);
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            // Keep snooze recoverable even if the user revoked exact-alarm access after the original alarm.
            manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi);
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            manager.setExact(AlarmManager.RTC_WAKEUP, triggerAt, pi);
        } else {
            manager.set(AlarmManager.RTC_WAKEUP, triggerAt, pi);
        }
        c.getSharedPreferences("dayflow_native", 0).edit()
                .putString("snooze_" + id, data.toString()).apply();
    }

    static void consumeSnooze(Context c, String id) {
        if (id == null || id.isEmpty()) return;
        PendingIntent pi = pendingSnooze(c, id, null,
                PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);
        if (pi != null) {
            AlarmManager manager = (AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
            if (manager != null) manager.cancel(pi);
            pi.cancel();
        }
        c.getSharedPreferences("dayflow_native", 0).edit().remove("snooze_" + id).apply();
    }

    static void restoreSnoozes(Context c) {
        android.content.SharedPreferences prefs = c.getSharedPreferences("dayflow_native", 0);
        for (String key : prefs.getAll().keySet()) {
            if (!key.startsWith("snooze_")) continue;
            String raw = prefs.getString(key, null);
            if (raw == null) continue;
            try {
                scheduleSnoozeData(c, new JSONObject(raw));
            } catch (Exception ignored) {
                // Keep the stored record so a later permission grant/time change can retry.
            }
        }
    }

    static void reschedule(Context c, String id) {''',
    "snooze scheduler methods",
)

# AlarmReceiver distinguishes the snooze PendingIntent and consumes its persistent record.
p = ROOT / "AlarmReceiver.java"
old = p.read_text(encoding="utf-8")
new = '''package app.dayflow.android;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public class AlarmReceiver extends BroadcastReceiver {
 @Override public void onReceive(Context context, Intent intent) {
  if (intent == null) return;
  String id=intent.getStringExtra("id"), label=intent.getStringExtra("label");
  String action=intent.getAction();
  if (id != null && action != null && action.startsWith("app.dayflow.android.ALARM_SNOOZE.")) {
   AlarmScheduler.consumeSnooze(context,id);
  }
  NativeNotifications.showAlarm(context, label == null ? "DAYFLOW alarm" : label, id,
      intent.getStringExtra("soundUri"), intent.getBooleanExtra("vibrate", true),
      intent.getIntExtra("snooze", 10));
  if (id != null) AlarmScheduler.reschedule(context,id);
 }
}
'''
if old != new:
    if "class AlarmReceiver extends BroadcastReceiver" not in old or "NativeNotifications.showAlarm(" not in old or "AlarmScheduler.reschedule(context,id)" not in old:
        raise SystemExit("AlarmReceiver has an unexpected structure; refusing an unsafe rewrite.")
    p.write_text(new, encoding="utf-8")

# Native alarm notification passes the selected snooze duration to the full-screen activity.
p = ROOT / "NativeNotifications.java"
replace_once(
    p,
    ' public static void showAlarm(Context c,String label,String id,String soundUri,boolean vibrate){',
    ' public static void showAlarm(Context c,String label,String id,String soundUri,boolean vibrate,int snoozeMinutes){',
    "showAlarm signature",
)
replace_once(
    p,
    '.putExtra("soundUri",sound.toString()).putExtra("vibrate",vibrate)',
    '.putExtra("soundUri",sound.toString()).putExtra("vibrate",vibrate).putExtra("snoozeMinutes",Math.max(0,snoozeMinutes))',
    "snooze duration on full-screen intent",
)

# Ring activity offers an actual snooze action; dismiss remains a separate action.
p = ROOT / "AlarmRingActivity.java"
replace_once(
    p,
    'import android.widget.TextView;\n',
    'import android.widget.TextView;\nimport android.widget.Toast;\n',
    "Toast import",
)
replace_once(
    p,
    '''        Button stop = new Button(this);
        stop.setText("Dismiss");
        stop.setOnClickListener(v -> dismissAlarm());
        layout.addView(title);
        layout.addView(stop);''',
    '''        Button stop = new Button(this);
        String uiLanguage = getResources().getConfiguration().locale.getLanguage();
        stop.setText("ar".equals(uiLanguage) ? "إيقاف" : "Dismiss");
        stop.setOnClickListener(v -> dismissAlarm());
        layout.addView(title);
        int snoozeMinutes = getIntent().getIntExtra("snoozeMinutes", 0);
        if (snoozeMinutes > 0) {
            Button snooze = new Button(this);
            snooze.setText("ar".equals(uiLanguage)
                    ? "غفوة " + snoozeMinutes + " دقيقة"
                    : "Snooze " + snoozeMinutes + " min");
            snooze.setOnClickListener(v -> snoozeAlarm(snoozeMinutes));
            layout.addView(snooze);
        }
        layout.addView(stop);''',
    "real snooze button",
)
replace_once(
    p,
    '''    private void dismissAlarm() {
        stopPlayback();''',
    '''    private void snoozeAlarm(int minutes) {
        try {
            AlarmScheduler.scheduleSnooze(this,
                    getIntent().getStringExtra("alarmId"),
                    getIntent().getStringExtra("label"),
                    getIntent().getStringExtra("soundUri"),
                    getIntent().getBooleanExtra("vibrate", true),
                    minutes);
            dismissAlarm();
        } catch (Exception error) {
            Toast.makeText(this,
                    "Could not schedule snooze. Check Alarms & reminders permission.",
                    Toast.LENGTH_LONG).show();
        }
    }

    private void dismissAlarm() {
        stopPlayback();''',
    "snooze handler",
)

# Restore reminders and snoozes even when exact-alarm special access was revoked.
p = ROOT / "BootReceiver.java"
boot = p.read_text(encoding="utf-8")
if "class BootReceiver" not in boot or "AlarmScheduler.restoreAll(context)" not in boot:
    raise SystemExit("BootReceiver has an unexpected structure; refusing an unsafe rewrite.")
boot = """package app.dayflow.android;
import android.app.AlarmManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        ReminderScheduler.restoreAll(context);
        AlarmScheduler.restoreSnoozes(context);
        AlarmManager manager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || (manager != null && manager.canScheduleExactAlarms())) {
            AlarmScheduler.restoreAll(context);
        }
    }
}
"""
p.write_text(boot, encoding="utf-8")

# Required postconditions prevent false success.
checks = {
    "AlarmScheduler.java": [
        "scheduleSnooze(Context c",
        "static void cancelSnooze(Context c, String id)",
        "restoreSnoozes(Context c)",
        "setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)",
        'remove("snooze_" + id)'
    ],
    "AlarmReceiver.java": [
        "ALARM_SNOOZE.",
        "intent.getIntExtra(\"snooze\", 10)",
        "AlarmScheduler.consumeSnooze(context,id)"
    ],
    "NativeNotifications.java": [
        "int snoozeMinutes)",
        'putExtra("snoozeMinutes",Math.max(0,snoozeMinutes))'
    ],
    "AlarmRingActivity.java": [
        "snoozeAlarm(snoozeMinutes)",
        "AlarmScheduler.scheduleSnooze(this"
    ],
    "BootReceiver.java": [
        "AlarmScheduler.restoreSnoozes(context)"
    ]
}
for filename, needles in checks.items():
    source = (ROOT / filename).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in source:
            raise SystemExit(f"{filename}: snooze postcondition missing: {needle}")

print("DAYFLOW native snooze scheduling, ringing UI, cancellation, and reboot restoration applied and verified.")
