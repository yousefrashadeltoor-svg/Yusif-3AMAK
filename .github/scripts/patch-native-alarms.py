#!/usr/bin/env python3
"""Idempotent DAYFLOW Android alarm bridge patch, run after Capacitor sync and native-source extraction."""
from pathlib import Path
import sys

root = Path.cwd()
src = root / "src"
native = root / "android/app/src/main/java/app/dayflow/android"
manifest = root / "android/app/src/main/AndroidManifest.xml"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Expected source marker not found: {label}")
    return text.replace(old, new, 1)

# 1) Register the exact-alarm permission methods on the Capacitor bridge.
p = native / "DayflowBridgePlugin.java"
s = p.read_text(encoding="utf-8")
methods = """    @PluginMethod public void canScheduleExactAlarms(PluginCall call) {
        boolean granted = Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            ((AlarmManager)getContext().getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms();
        JSObject out = new JSObject(); out.put("granted", granted); call.resolve(out);
    }

    @PluginMethod public void requestExactAlarmPermission(PluginCall call) {
        boolean granted = Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            ((AlarmManager)getContext().getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms();
        if (!granted && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            Intent settings = new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                Uri.parse("package:" + getContext().getPackageName()));
            settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(settings);
        }
        JSObject out = new JSObject(); out.put("granted", granted);
        out.put("settingsOpened", !granted); call.resolve(out);
    }

"""
if "canScheduleExactAlarms(PluginCall call)" not in s:
    s = replace_once(s, "    @PluginMethod public void scheduleAlarm(PluginCall call) {",
                     methods + "    @PluginMethod public void scheduleAlarm(PluginCall call) {",
                     "Capacitor exact-alarm methods")
p.write_text(s, encoding="utf-8")

# 2) Enforce the Android special access and use immutable PendingIntents consistently.
p = native / "AlarmScheduler.java"
s = p.read_text(encoding="utf-8")
s = s.replace("PendingIntent pi = pending(c, id, null, PendingIntent.FLAG_NO_CREATE);",
              "PendingIntent pi = pending(c, id, null, PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);")
guard = """        AlarmManager am = (AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
            throw new SecurityException("Grant Alarms & reminders access before scheduling an exact alarm");
        }
        if (Build.VERSION.SDK_INT >= 23) {"""
old = """        AlarmManager am = (AlarmManager)c.getSystemService(Context.ALARM_SERVICE);
        if (Build.VERSION.SDK_INT >= 23) {"""
s = replace_once(s, old, guard, "AlarmManager exact-permission guard")
# A one-time alarm must not remain in persistent storage after it fires.
old = """        String raw = c.getSharedPreferences("dayflow_native",0).getString("alarm_"+id,null);
        if (raw == null) return;
        try { schedule(c,new JSONObject(raw)); } catch (Exception ignored) {}"""
new = """        String key = "alarm_" + id;
        String raw = c.getSharedPreferences("dayflow_native",0).getString(key,null);
        if (raw == null) return;
        try {
            JSONObject data = new JSONObject(raw);
            JSONArray days = data.optJSONArray("days");
            if (days == null || days.length() == 0) {
                c.getSharedPreferences("dayflow_native",0).edit().remove(key).apply();
                return;
            }
            schedule(c, data);
        } catch (Exception ignored) {}"""
s = replace_once(s, old, new, "one-time alarm cleanup")
p.write_text(s, encoding="utf-8")

# 3) Deliver the selected device ringtone and vibration with the alarm broadcast.
p = native / "AlarmReceiver.java"
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    'NativeNotifications.showAlarm(context, label == null ? "DAYFLOW alarm" : label, id);',
    'NativeNotifications.showAlarm(context, label == null ? "DAYFLOW alarm" : label, id, intent.getStringExtra("soundUri"), intent.getBooleanExtra("vibrate", true));',
    "alarm receiver sound and vibration"
)
p.write_text(s, encoding="utf-8")

# 4) Configure an alarm-specific notification channel so Android uses the selected sound.
p = native / "NativeNotifications.java"
s = p.read_text(encoding="utf-8")
for imp in [
    "import android.media.AudioAttributes;",
    "import android.net.Uri;",
    "import android.provider.Settings;"
]:
    if imp not in s:
        s = s.replace("import android.os.Build;", "import android.os.Build;\n" + imp, 1)
start = s.find(" public static void showAlarm(")
if start < 0:
    raise RuntimeError("NativeNotifications.showAlarm method not found")
end = s.find("\n }", start)
if end < 0:
    raise RuntimeError("NativeNotifications.showAlarm method end not found")
end += len("\n }")
alarm_method = """ public static void showAlarm(Context c,String label,String id,String soundUri,boolean vibrate){
  Uri sound = (soundUri == null || soundUri.isEmpty())
      ? Settings.System.DEFAULT_ALARM_ALERT_URI : Uri.parse(soundUri);
  String channelId = "dayflow_alarm_" + (id == null ? "default" : id.hashCode())
      + "_" + sound.toString().hashCode() + "_" + (vibrate ? "v" : "n");
  if (Build.VERSION.SDK_INT >= 26) {
   NotificationManager nm=(NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE);
   if (nm.getNotificationChannel(channelId) == null) {
    NotificationChannel ch=new NotificationChannel(channelId,"DAYFLOW alarm",NotificationManager.IMPORTANCE_HIGH);
    ch.setSound(sound,new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
    ch.enableVibration(vibrate);
    ch.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
    nm.createNotificationChannel(ch);
   }
  }
  Intent open=new Intent(c,AlarmRingActivity.class).putExtra("label",label).putExtra("alarmId",id)
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP);
  PendingIntent pi=PendingIntent.getActivity(c,(id==null?7100:id.hashCode()),open,
      PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
  Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(c,channelId):new Notification.Builder(c);
  b.setSmallIcon(c.getApplicationInfo().icon).setContentTitle(label).setContentText("Alarm is ringing")
      .setCategory(Notification.CATEGORY_ALARM).setPriority(Notification.PRIORITY_MAX)
      .setFullScreenIntent(pi,true).setContentIntent(pi).setOngoing(true).setAutoCancel(false);
  if (Build.VERSION.SDK_INT < 26) { b.setSound(sound); if (vibrate) b.setVibrate(new long[]{0,500,250,500}); }
  ((NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE)).notify(id==null?7100:id.hashCode(),b.build());
 }"""
s = s[:start] + alarm_method + s[end:]
p.write_text(s, encoding="utf-8")

# 5) Stop the active alarm notification when the user dismisses the ringing screen.
p = native / "AlarmRingActivity.java"
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    "stop.setOnClickListener(v->{finish();});",
    'stop.setOnClickListener(v->{String id=getIntent().getStringExtra("alarmId");((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).cancel(id==null?7100:id.hashCode());finish();});',
    "alarm notification dismissal"
)
p.write_text(s, encoding="utf-8")

# 6) Restore scheduled alarms after exact-alarm access is granted or the device restarts.
p = native / "BootReceiver.java"
s = p.read_text(encoding="utf-8")
if "import android.app.AlarmManager;" not in s:
    s = s.replace("import android.content.Intent;", "import android.content.Intent;\nimport android.app.AlarmManager;")
if "import android.os.Build;" not in s:
    s = s.replace("import android.app.AlarmManager;", "import android.app.AlarmManager;\nimport android.os.Build;")
s = replace_once(
    s,
    "public class BootReceiver extends BroadcastReceiver {\n @Override public void onReceive(Context context, Intent intent) { AlarmScheduler.restoreAll(context); }",
    "public class BootReceiver extends BroadcastReceiver {\n @Override public void onReceive(Context context, Intent intent) { if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !((AlarmManager)context.getSystemService(Context.ALARM_SERVICE)).canScheduleExactAlarms()) return; AlarmScheduler.restoreAll(context); }",
    "boot and exact-alarm permission restoration"
)
p.write_text(s, encoding="utf-8")

# 7) Listen for Android's exact-alarm grant broadcast.
if not manifest.exists():
    raise RuntimeError("AndroidManifest.xml not found")
m = manifest.read_text(encoding="utf-8")
exact_action = '<action android:name="android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED"/>'
time_action = '<action android:name="android.intent.action.TIMEZONE_CHANGED"/>'
if exact_action not in m:
    if time_action not in m:
        raise RuntimeError("BootReceiver time-zone intent filter not found")
    m = m.replace(time_action, time_action + exact_action, 1)
manifest.write_text(m, encoding="utf-8")

# 8) Expose the exact-alarm APIs through the Capacitor 8 TypeScript bridge.
p = src / "lib/nativeBridge.ts"
s = p.read_text(encoding="utf-8")
if "canScheduleExactAlarms():" not in s:
    s = replace_once(
        s,
        '            scheduleAlarm(opts: { id:string; time:string; date?:string; days:number[]; label:string; soundUri?:string; vibrate:boolean; snooze:number; enabled?:boolean }): Promise<{scheduled?:boolean}>;',
        '            scheduleAlarm(opts: { id:string; time:string; date?:string; days:number[]; label:string; soundUri?:string; vibrate:boolean; snooze:number; enabled?:boolean }): Promise<{scheduled?:boolean}>;\\n            canScheduleExactAlarms(): Promise<{granted:boolean}>;\\n            requestExactAlarmPermission(): Promise<{granted:boolean;settingsOpened?:boolean}>;',
        "native bridge exact-alarm interface"
    )
    s = replace_once(
        s,
        '            scheduleAlarm:(o:Parameters<DayflowNative["scheduleAlarm"]>[0])=>call("scheduleAlarm",o),',
        '            scheduleAlarm:(o:Parameters<DayflowNative["scheduleAlarm"]>[0])=>call("scheduleAlarm",o),\\n            canScheduleExactAlarms:()=>call("canScheduleExactAlarms"),\\n            requestExactAlarmPermission:()=>call("requestExactAlarmPermission"),',
        "native bridge exact-alarm methods"
    )
p.write_text(s, encoding="utf-8")

# 9) Keep the selected Android sound URI in app state and pass it to Android scheduling.
p = src / "lib/store.ts"
s = p.read_text(encoding="utf-8")
s = s.replace("sound: { source: SoundSource; title: string }", "sound: { source: SoundSource; title: string; uri?: string }")
p.write_text(s, encoding="utf-8")

p = src / "screens/Alarms.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace('import { nativeBridge } from "../lib/nativeBridge";',
              'import { nativeBridge, isAndroidApk } from "../lib/nativeBridge";')
# Device tone URIs are retained, not just their display names.
s = s.replace("const [nativeTones, setNativeTones] = useState<string[] | null>(null);",
              "const [nativeTones, setNativeTones] = useState<Array<{ title: string; uri: string }> | null>(null);")
s = s.replace("setNativeTones(r.tones.map((x) => x.title))",
              "setNativeTones(r.tones.map((x) => ({ title: x.title, uri: x.uri })))")
s = s.replace(
    'const device = nativeTones || [t("Default alarm (device)", "منبه الجهاز الافتراضي"), t("Default ringtone (device)", "نغمة الرنين الافتراضية"), t("Default notification (device)", "صوت الإشعار الافتراضي")];',
    'const device = nativeTones || [t("Default alarm (device)", "منبه الجهاز الافتراضي"), t("Default ringtone (device)", "نغمة الرنين الافتراضية"), t("Default notification (device)", "صوت الإشعار الافتراضي")].map(title => ({ title, uri: "" }));'
)
s = s.replace(
    '{device.map((d) => <button key={d} onClick={() => onPick({ source: "device", title: d })}',
    '{device.map((d) => <button key={d.uri || d.title} onClick={() => onPick({ source: "device", title: d.title, uri: d.uri })}'
)
s = s.replace('<span className="flex-1">{d}</span>{value.title === d &&',
              '<span className="flex-1">{d.title}</span>{value.title === d.title &&')

# Hide browser-only alarm warning in the native Android app.
browser_warning = '<div className="mt-5"><Honest>{t("This preview runs in a browser, so it can\'t ring when it\'s closed. On Android, alarms are scheduled natively with setAlarmClock() and ring even if the app is closed.", "هذه النسخة تعمل في المتصفح ولا يمكنها الرنين وهي مغلقة. على أندرويد تُجدول المنبهات أصليًا عبر setAlarmClock() وترن حتى لو كان التطبيق مغلقًا.")}</Honest></div>'
if browser_warning in s:
    s = s.replace(browser_warning, '{!isAndroidApk() && ' + browser_warning + '}')

s = s.replace("const save = () => {", "const save = async () => {")
date_anchor = '    if (a.date && (!isValidDay(a.date) || !futureAt(a.date, a.time))) { setError(t("That date and time have already passed. Pick a future time.", "المعاد ده فات؛ اختار يوم وساعة لسه جايين.")); return; }'
permission_ui = """
    if (a.enabled && isAndroidApk()) {
      const permission = await nativeBridge.canScheduleExactAlarms?.();
      if (permission && !permission.granted) {
        await nativeBridge.requestExactAlarmPermission?.();
        setError(t("Allow DAYFLOW to set alarms and reminders in Android Settings, then tap Save again.", "اسمح لـ DAYFLOW بضبط المنبهات والتذكيرات من إعدادات أندرويد، وبعدها اضغط حفظ مرة تانية."));
        return;
      }
    }"""
if "canScheduleExactAlarms" not in s:
    s = replace_once(s, date_anchor, date_anchor + permission_ui, "alarm save permission prompt")

# Support both original and already soundUri-patched forms.
old_persist = """    const id = a.id ? (s.updateAlarm(a.id, a), a.id) : s.addAlarm(a);
    if (a.enabled) void nativeBridge.scheduleAlarm({ id, date: a.date, time: a.time, days: a.days, label: a.label, vibrate: a.vibrate, snooze: a.snooze });
    else nativeBridge.cancelAlarm({ id });
    onClose();"""
new_persist = """    const id = a.id ? (s.updateAlarm(a.id, a), a.id) : s.addAlarm(a);
    if (!a.id) setA({ ...a, id });
    try {
      if (a.enabled) await nativeBridge.scheduleAlarm({ id, date: a.date, time: a.time, days: a.days, label: a.label, soundUri: a.sound.uri, vibrate: a.vibrate, snooze: a.snooze });
      else await nativeBridge.cancelAlarm({ id });
    } catch (e) {
      setError(t("Android could not schedule this alarm. Check Alarms & reminders access and try again.", "أندرويد لم يستطع جدولة المنبه. راجع إذن المنبهات والتذكيرات وحاول مرة أخرى."));
      return;
    }
    onClose();"""
old_persist_sound = old_persist.replace("label: a.label, vibrate:", "label: a.label, soundUri: a.sound.uri, vibrate:")
if old_persist in s:
    s = s.replace(old_persist, new_persist)
elif old_persist_sound in s:
    s = s.replace(old_persist_sound, new_persist)
elif "await nativeBridge.scheduleAlarm({ id, date: a.date" not in s:
    raise RuntimeError("AlarmEditor save scheduling block not found")
# Guard the enabled switch too; don't show enabled when Android rejects the request.
toggle_old = 'onChange={(v) => { s.updateAlarm(a.id, { enabled: v }); if (v) void nativeBridge.scheduleAlarm({ id: a.id, date: a.date, time: a.time, days: a.days, label: a.label, vibrate: a.vibrate, snooze: a.snooze }); else void nativeBridge.cancelAlarm({ id: a.id }); }}'
toggle_old_sound = toggle_old.replace("label: a.label, vibrate:", "label: a.label, soundUri: a.sound.uri, vibrate:")
toggle_new = 'onChange={async (v) => { if (v && isAndroidApk()) { const permission = await nativeBridge.canScheduleExactAlarms?.(); if (permission && !permission.granted) { await nativeBridge.requestExactAlarmPermission?.(); return; } } try { if (v) await nativeBridge.scheduleAlarm({ id: a.id, date: a.date, time: a.time, days: a.days, label: a.label, soundUri: a.sound.uri, vibrate: a.vibrate, snooze: a.snooze }); else await nativeBridge.cancelAlarm({ id: a.id }); s.updateAlarm(a.id, { enabled: v }); } catch (e) { console.error("DAYFLOW alarm scheduling failed", e); } }}'
if toggle_old in s:
    s = s.replace(toggle_old, toggle_new)
elif toggle_old_sound in s:
    s = s.replace(toggle_old_sound, toggle_new)
p.write_text(s, encoding="utf-8")

print("Native alarm patch applied and verified.")
