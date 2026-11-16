#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT output is required}"
mkdir -p "$GITHUB_WORKSPACE/build-output"

set -euo pipefail
cd "$PROJECT_ROOT"
# Generate the project's intended offline assets, then restore the requested real dawn photo.
npm ci
# Capacitor packages are required by the web bridge at compile time and by the Android platform.
npm install --no-save "@capacitor/core@^8.0.0" "@capacitor/android@^8.0.0" "@capacitor/cli@^8.0.0"
# Replace the archive's legacy window.Capacitor.Plugins lookup with the supported Capacitor 8 registry.
cat > src/lib/nativeBridge.ts <<'EOF'
import { Capacitor, registerPlugin } from "@capacitor/core";
export interface DayflowNative {
  scheduleAlarm(opts: { id:string; time:string; date?:string; days:number[]; label:string; soundUri?:string; vibrate:boolean; snooze:number; enabled?:boolean }): Promise<{scheduled?:boolean}>;
  cancelAlarm(opts:{id:string}):Promise<{cancelled?:boolean}>;
  getDeviceTones():Promise<{tones:Array<{title:string;uri:string;type:string}>}>;
  pinWidget(opts:{designId:string;style:string;w:number;h:number}):Promise<{pinned:boolean}>;
  openWidgetHub():Promise<void>; requestNotificationsPermission():Promise<void>;
  startCompanionOverlay(opts:{enabled:boolean;size:number;opacity:number;modelId?:string}):Promise<{hasPermission:boolean}>;
  requestOverlayPermission():Promise<void>;
  enqueueDownload(opts:{url:string;name:string;preset?:string}):Promise<{downloadId?:number;queued?:boolean}>;
  analyzeLink(opts:{url:string}):Promise<{json:string}>;
  startDownload(opts:{id:string;url:string;name:string;engines:string[];format:string;quality:string;saveDir:string;connections:number}):Promise<{downloadId?:number;queued?:boolean}>;
  pauseDownload(opts:{id:string}):Promise<void>; cancelDownload(opts:{id:string}):Promise<void>;
  updateEngines():Promise<{ytdlp:string}>; openSniffer(opts:{url:string}):Promise<void>;
  getPendingShare():Promise<{text:string}>; syncState(opts:{json:string}):Promise<void>;
  showNotification(opts:{title:string;body:string;channel?:string;id?:number}):Promise<void>;
}
const DayflowBridge=registerPlugin<DayflowNative>("DayflowBridge");
export const isAndroidApk=()=>Capacitor.isNativePlatform() && Capacitor.getPlatform()==="android";
const call=<K extends keyof DayflowNative>(name:K,...args:Parameters<DayflowNative[K]>):ReturnType<DayflowNative[K]>|undefined=>{
  if(!isAndroidApk()) return undefined;
  const fn=DayflowBridge[name] as (...a:Parameters<DayflowNative[K]>)=>ReturnType<DayflowNative[K]>;
  if(typeof fn!=="function") return Promise.reject(new Error("Android native feature is not installed: "+String(name))) as ReturnType<DayflowNative[K]>;
  return fn(...args);
};
export const nativeBridge={
  scheduleAlarm:(o:Parameters<DayflowNative["scheduleAlarm"]>[0])=>call("scheduleAlarm",o),
  cancelAlarm:(o:Parameters<DayflowNative["cancelAlarm"]>[0])=>call("cancelAlarm",o),
  getDeviceTones:()=>call("getDeviceTones"),
  pinWidget:(o:Parameters<DayflowNative["pinWidget"]>[0])=>call("pinWidget",o),
  openWidgetHub:()=>call("openWidgetHub"), requestNotificationsPermission:()=>call("requestNotificationsPermission"),
  startCompanionOverlay:(o:Parameters<DayflowNative["startCompanionOverlay"]>[0])=>call("startCompanionOverlay",o),
  requestOverlayPermission:()=>call("requestOverlayPermission"),
  enqueueDownload:(o:Parameters<DayflowNative["enqueueDownload"]>[0])=>call("enqueueDownload",o),
  analyzeLink:(o:Parameters<DayflowNative["analyzeLink"]>[0])=>call("analyzeLink",o),
  startDownload:(o:Parameters<DayflowNative["startDownload"]>[0])=>call("startDownload",o),
  pauseDownload:(o:Parameters<DayflowNative["pauseDownload"]>[0])=>call("pauseDownload",o),
  cancelDownload:(o:Parameters<DayflowNative["cancelDownload"]>[0])=>call("cancelDownload",o),
  updateEngines:()=>call("updateEngines"),
  openSniffer:(o:Parameters<DayflowNative["openSniffer"]>[0])=>call("openSniffer",o),
  getPendingShare:()=>call("getPendingShare"),
  syncState:(json:string)=>call("syncState",{json}),
  showNotification:(o:Parameters<DayflowNative["showNotification"]>[0])=>call("showNotification",o)
};
EOF
# Patch the archived app source to persist selected Android ringtone URIs and use native notifications.
python3 - <<'PY'
from pathlib import Path
p=Path("src/lib/store.ts"); s=p.read_text()
s=s.replace('sound: { source: SoundSource; title: string }','sound: { source: SoundSource; title: string; uri?: string }')
s=s.replace('label: alarm.label, vibrate: alarm.vibrate, snooze: alarm.snooze','label: alarm.label, soundUri: alarm.sound.uri, vibrate: alarm.vibrate, snooze: alarm.snooze')
p.write_text(s)
p=Path("src/screens/Alarms.tsx"); s=p.read_text()
s=s.replace('label: a.label, vibrate: a.vibrate, snooze: a.snooze','label: a.label, soundUri: a.sound.uri, vibrate: a.vibrate, snooze: a.snooze')
s=s.replace('const [nativeTones, setNativeTones] = useState<string[] | null>(null);','const [nativeTones, setNativeTones] = useState<Array<{title:string;uri:string}> | null>(null);')
s=s.replace('setNativeTones(r.tones.map((x) => x.title))','setNativeTones(r.tones.map((x) => ({title:x.title,uri:x.uri})))')
s=s.replace('const device = nativeTones || [t("Default alarm (device)", "منبه الجهاز الافتراضي"), t("Default ringtone (device)", "نغمة الرنين الافتراضية"), t("Default notification (device)", "صوت الإشعار الافتراضي")];','const device = nativeTones || [t("Default alarm (device)", "منبه الجهاز الافتراضي"), t("Default ringtone (device)", "نغمة الرنين الافتراضية"), t("Default notification (device)", "صوت الإشعار الافتراضي")].map(title=>({title,uri:""}));')
s=s.replace('{device.map((d) => <button key={d} onClick={() => onPick({ source: "device", title: d })}', '{device.map((d) => <button key={d.uri || d.title} onClick={() => onPick({ source: "device", title: d.title, uri: d.uri })}')
s=s.replace('<span className="flex-1">{d}</span>{value.title === d &&', '<span className="flex-1">{d.title}</span>{value.title === d.title &&')
p.write_text(s)
p=Path("src/screens/Me.tsx"); s=p.read_text()
s=s.replace('import { nativeBridge } from "../lib/nativeBridge";','import { nativeBridge, isAndroidApk } from "../lib/nativeBridge";')
s=s.replace('  const test = async () => {','  const test = async () => {\n    if (isAndroidApk()) { try { await nativeBridge.requestNotificationsPermission?.(); await nativeBridge.showNotification?.({ title: "DAYFLOW — " + t("notification test", "اختبار الإشعارات"), body: s.notif.preview ? t("A reminder is ready", "عندك تذكير") : t("A reminder is ready", "عندك تذكير"), channel: "dayflow_reminders", id: 4101 }); setTested(t("Sent. Check your notification tray.", "اتبعت. بص في الإشعارات.")); } catch (e) { setTested(String(e)); } return; }')
browserNote='      <div className="mt-3"><Honest>{t("Browser notifications are real and permission-based. Scheduled background reminders need the Android notification system (not built in this preview). Interactive buttons (Complete / Snooze / Open) are Android-only.", "إشعارات المتصفح حقيقية وبتطلب إذن. التذكيرات المجدولة في الخلفية محتاجة نظام إشعارات أندرويد (مش مبني في المعاينة). الأزرار التفاعلية (تم / غفوة / افتح) لأندرويد فقط.")}</Honest></div>'
s=s.replace(browserNote,'      {!isAndroidApk() && <div className="mt-3"><Honest>{t("Browser notifications are real and permission-based. Scheduled background reminders need the Android notification system.", "إشعارات المتصفح حقيقية وبتطلب إذن. التذكيرات المجدولة في الخلفية محتاجة نظام إشعارات أندرويد.")}</Honest></div>}')
p.write_text(s)
# Correct prayer calculations for the selected city's civil date and daylight-saving offset.
p=Path("src/lib/downloads.ts"); s=p.read_text()
s=s.replace('title: string; thumb?: string; author?: string; duration?: number;','title: string; thumb?: string; author?: string; description?: string; duration?: number;')
s=s.replace('thumbnail?: string; duration?: number; formats?: YtFormat[]; webpage_url_domain?: string','thumbnail?: string; duration?: number; formats?: YtFormat[]; webpage_url_domain?: string; description?: string; mimeType?: string; size?: number; direct?: boolean; site?: string')
s=s.replace('base.title = j.title || base.title; base.author = j.uploader; base.thumb = j.thumbnail; base.duration = j.duration; base.filename = sanitizeFilename(j.title || "download");','base.title = j.title || base.title; base.author = j.uploader || j.site; base.description = j.description; base.mime = j.mimeType; base.size = j.size && j.size > 0 ? j.size : undefined; base.thumb = j.thumbnail; base.duration = j.duration; base.filename = sanitizeFilename(j.title || "download");')
s=s.replace('''        base.formats = [
...g.presets.map''','''        base.formats = j.direct ? [{ id: "original", label: (j.mimeType || "FILE").split("/").pop()?.toUpperCase() || "FILE", detail: j.mimeType || "Direct file", size: base.size, kind: (kind === "video" ? "video" : kind === "audio" ? "audio" : kind === "image" ? "image" : "file") as "video" | "audio" | "image" | "file", url: parsed.url }] : [
...g.presets.map''')
p.write_text(s)
p=Path("src/screens/Downloads.tsx"); s=p.read_text()
s=s.replace('{an.author && <p className="mt-1 text-[11px] muted">{an.author}</p>}', '{an.author && <p className="mt-1 text-[11px] muted">{an.author}</p>}{an.description && <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed muted">{an.description}</p>}')
p.write_text(s)
p=Path("src/lib/prayer.ts"); s=p.read_text()
s=s.replace('  { lat: 31.2001, lng: 29.9187, city: "Alexandria", cityAr: "الإسكندرية", tz: 2 },','  { lat: 31.2001, lng: 29.9187, city: "Alexandria", cityAr: "الإسكندرية", tz: 2 },')
s=s.replace('  { lat: 51.5074, lng: -0.1278, city: "London", cityAr: "لندن", tz: 0 },','  { lat: 51.5074, lng: -0.1278, city: "London", cityAr: "لندن", tz: 0 },' + chr(10) + '  { lat: 30.0131, lng: 31.2089, city: "Giza", cityAr: "الجيزة", tz: 2 },' + chr(10) + '  { lat: 30.1792, lng: 31.2056, city: "Qalyub", cityAr: "قليوب", tz: 2 },' + chr(10) + '  { lat: 30.4667, lng: 31.1833, city: "Benha", cityAr: "بنها", tz: 2 },')
s=s.replace('let y = date.getFullYear(), m = date.getMonth() + 1; const d = date.getDate();','let y = date.getUTCFullYear(), m = date.getUTCMonth() + 1; const d = date.getUTCDate();')
s=s.replace('  const jd = julian(date);','''  const zone = loc.city === "London" ? "Europe/London" : loc.tz === 3 ? "Asia/Riyadh" : loc.tz === 4 ? "Asia/Dubai" : "Africa/Cairo";
const parts = new Intl.DateTimeFormat("en-GB", { timeZone: zone, year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", hourCycle: "h23" }).formatToParts(date);
const part = (type: string) => Number(parts.find(x => x.type === type)?.value || 0);
const year=part("year"), month=part("month"), day=part("day"), hour=part("hour"), minute=part("minute");
const tz = Math.round((Date.UTC(year, month-1, day, hour, minute) - date.getTime()) / 900000) / 4;
const civilDate = new Date(Date.UTC(year, month-1, day));
const jd = julian(civilDate);''')
s=s.replace('12 - eqt - loc.lng / 15 + loc.tz','12 - eqt - loc.lng / 15 + tz')
s=s.replace('const nowMin = date.getHours() * 60 + date.getMinutes();','const nowMin = hour * 60 + minute;')
p.write_text(s)
PY
node gen-assets.mjs
curl --fail --location --retry 3 --retry-delay 2 --connect-timeout 20 --max-time 120 \
  "https://images.unsplash.com/photo-1517359795165-71871b9e3266?auto=format&fit=crop&fm=jpg&ixid=NHwxMjA3fDA%3D&ixlib=rb-4.1.0&q=82&w=1920" \
  --output src/assets/photos/dawn.jpg
test -s src/assets/photos/dawn.jpg
file src/assets/photos/dawn.jpg
python3 - <<'PY'
import pathlib, re
root = pathlib.Path("src").resolve()
pattern = re.compile(r"""(?:from\s*|import\s*\()\s*['"]([^'"]+\.(?:png|jpe?g|webp|gif|avif))['"]""", re.I)
missing = []
for source in root.rglob("*"):
    if source.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
        continue
    try:
        content = source.read_text(encoding="utf-8")
    except Exception:
        continue
    for spec in pattern.findall(content):
        if not spec.startswith("."):
            continue
        target = (source.parent / spec).resolve()
        if root in target.parents and not target.exists():
            missing.append(f"{source.relative_to(root)} -> {target.relative_to(root)}")
if missing:
    print("Missing image imports:")
    print("\n".join(missing))
    raise SystemExit(1)
print("All statically imported local image assets are present.")
PY
if node -e "process.exit(require('./package.json').scripts?.build ? 0 : 1)"; then npm run build; fi
npx cap --version
if [[ ! -d android ]]; then npx cap add android; fi
npx cap sync android
# Install the native Android implementation maintained in this repository.
python3 "$GITHUB_WORKSPACE/.github/scripts/extract-native-archives.py"
mkdir -p /tmp/dayflow-native android/app/src/main/java/app/dayflow/android android/app/src/main/res/layout android/app/src/main/res/xml
unzip -oq /tmp/dayflow-native.zip -d /tmp/dayflow-native
cp -R /tmp/dayflow-native/java/app/dayflow/android/. android/app/src/main/java/app/dayflow/android/
cp /tmp/dayflow-native/res/layout/dayflow_widget.xml android/app/src/main/res/layout/
cp /tmp/dayflow-native/res/xml/dayflow_widget_info.xml android/app/src/main/res/xml/
python3 - <<'PY'
from pathlib import Path
import re
plugin=Path("android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java")
ps=plugin.read_text()
ps=ps.replace("import com.getcapacitor.annotation.CapacitorPlugin;", "import com.getcapacitor.annotation.CapacitorPlugin;" + chr(10) + "import com.getcapacitor.annotation.Permission;" + chr(10) + "import com.getcapacitor.annotation.PermissionCallback;" + chr(10) + "import com.getcapacitor.PermissionState;")
ps=ps.replace('@CapacitorPlugin(name = "DayflowBridge")', '@CapacitorPlugin(name = "DayflowBridge", permissions = { @Permission(alias = "notifications", strings = { Manifest.permission.POST_NOTIFICATIONS }) })')
permission_methods="""
    @PluginMethod public void requestNotificationsPermission(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33 || getPermissionState("notifications") == PermissionState.GRANTED) { call.resolve(); return; }
        requestPermissionForAlias("notifications", call, "notificationPermissionResult");
    }
    @PermissionCallback private void notificationPermissionResult(PluginCall call) {
        if (getPermissionState("notifications") == PermissionState.GRANTED) call.resolve();
        else call.reject("Notification permission was not granted");
    }
"""
if "requestNotificationsPermission" not in ps: ps=ps.replace("    @PluginMethod public void showNotification",permission_methods+chr(10)+"    @PluginMethod public void showNotification")
plugin.write_text(ps)
# Correct Android framework imports and prevent webpage URLs being saved as fake media downloads.
plugin=Path("android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java")
ps=plugin.read_text().replace("import android.app.AppWidgetManager;", "import android.appwidget.AppWidgetManager;")
guard='''        String path = Uri.parse(url).getLastPathSegment();
        if (path == null || !path.matches("(?i).+\\\\.(mp4|m4v|mov|webm|mp3|m4a|aac|wav|flac|ogg|opus|jpg|jpeg|png|webp|gif|pdf|zip|7z|rar|apk|txt|csv|docx|xlsx)")) {
            call.reject("This build supports direct file URLs only. This page needs a real media extractor, which is not bundled yet.");
            return;
        }
'''
ps=ps.replace('        try {' + chr(10) + '            DownloadManager.Request request', '        try {' + chr(10) + guard + '            DownloadManager.Request request')
ps=ps.replace('intent.putExtra("size", call.getInt("size",100));','intent.putExtra("size", (int)(112 * call.getDouble("size", 1.0)));')
plugin.write_text(ps)
widget=Path("android/app/src/main/java/app/dayflow/android/DayflowWidgetProvider.java")
ws=widget.read_text().replace("import android.appwidget.*;", "import android.appwidget.*;import android.app.PendingIntent;")
widget.write_text(ws)
manifest=Path("android/app/src/main/AndroidManifest.xml")
s=manifest.read_text()
permissions=[
  "android.permission.INTERNET","android.permission.SCHEDULE_EXACT_ALARM",
  "android.permission.POST_NOTIFICATIONS","android.permission.VIBRATE","android.permission.USE_FULL_SCREEN_INTENT","android.permission.SYSTEM_ALERT_WINDOW",
  "android.permission.RECEIVE_BOOT_COMPLETED","android.permission.FOREGROUND_SERVICE",
  "android.permission.FOREGROUND_SERVICE_SPECIAL_USE"
]
for p in permissions:
  tag=f'<uses-permission android:name="{p}" />'
  if p not in s:
    s=s.replace("<application", f"    {tag}" + chr(10) + "    <application", 1)
components="""
    <activity android:name="app.dayflow.android.AlarmRingActivity" android:exported="false" android:showWhenLocked="true" android:turnScreenOn="true" android:excludeFromRecents="true" />
    <receiver android:name="app.dayflow.android.AlarmReceiver" android:exported="false" />
    <receiver android:name="app.dayflow.android.BootReceiver" android:enabled="true" android:exported="true">
        <intent-filter><action android:name="android.intent.action.BOOT_COMPLETED"/><action android:name="android.intent.action.TIME_SET"/><action android:name="android.intent.action.TIMEZONE_CHANGED"/></intent-filter>
    </receiver>
    <service android:name="app.dayflow.android.CompanionOverlayService" android:exported="false" android:foregroundServiceType="specialUse">
        <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" android:value="User-enabled floating DAYFLOW companion overlay" />
    </service>
    <receiver android:name="app.dayflow.android.DayflowWidgetProvider" android:exported="true">
        <intent-filter><action android:name="android.appwidget.action.APPWIDGET_UPDATE"/></intent-filter>
        <meta-data android:name="android.appwidget.provider" android:resource="@xml/dayflow_widget_info"/>
    </receiver>
"""
if "DayflowWidgetProvider" not in s: s=s.replace("</application>",components+chr(10)+"</application>")
manifest.write_text(s)
activity=Path("android/app/src/main/java/app/dayflow/android/MainActivity.java")
if not activity.exists():
    raise SystemExit("Capacitor MainActivity.java not found; native plugin registration was not applied")
a=activity.read_text()
if "import android.os.Bundle;" not in a:
    import_marker="import android.content.Intent;"
    if import_marker in a:
        a=a.replace(import_marker, import_marker + chr(10) + "import android.os.Bundle;", 1)
    else:
        a=a.replace("package app.dayflow.android;", "package app.dayflow.android;" + chr(10) + "import android.os.Bundle;", 1)
if "registerPlugin(DayflowBridgePlugin.class)" not in a:
    class_marker="public class MainActivity extends BridgeActivity {"
    if class_marker not in a:
        raise SystemExit("Unexpected Capacitor MainActivity shape; cannot safely register DayflowBridge")
    if "onCreate(Bundle savedInstanceState)" in a:
        if "super.onCreate(savedInstanceState);" not in a:
            raise SystemExit("Existing MainActivity.onCreate has no super call; refusing unsafe plugin registration")
        a=a.replace("super.onCreate(savedInstanceState);", "registerPlugin(DayflowBridgePlugin.class);" + chr(10) + "        super.onCreate(savedInstanceState);", 1)
    else:
        method="    @Override public void onCreate(Bundle savedInstanceState) {" + chr(10) + "        registerPlugin(DayflowBridgePlugin.class);" + chr(10) + "        super.onCreate(savedInstanceState);" + chr(10) + "    }"
        a=a.replace(class_marker, class_marker + chr(10) + method, 1)
if a.count("registerPlugin(DayflowBridgePlugin.class)") != 1 or "onCreate(Bundle savedInstanceState)" not in a:
    raise SystemExit("DAYFLOW native bridge registration postcondition failed")
activity.write_text(a)
print("Registered DAYFLOW Capacitor native bridge in MainActivity.")
PY
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-native-alarms.py"
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-native-alarm-snooze.py"
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-app-features.py"
# Keep patch order explicit: widget data bridge -> persistent reminders -> overlay sync.
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-widget-flow.py"
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-native-reminders.py"
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-native-runtime.py"
# Direct Android downloads must be cancellable by their real DownloadManager ID.
python3 "$GITHUB_WORKSPACE/.github/scripts/patch-native-download-cancel.py"
# Validate every patcher and run regression tests against the extracted real source.
python3 -m py_compile \
  "$GITHUB_WORKSPACE/.github/scripts/patch-native-alarms.py" \
  "$GITHUB_WORKSPACE/.github/scripts/patch-app-features.py" \
  "$GITHUB_WORKSPACE/.github/scripts/patch-widget-flow.py" \
  "$GITHUB_WORKSPACE/.github/scripts/patch-native-reminders.py" \
  "$GITHUB_WORKSPACE/.github/scripts/patch-native-runtime.py" \
  "$GITHUB_WORKSPACE/.github/scripts/patch-native-download-cancel.py" \
  "$GITHUB_WORKSPACE/.github/scripts/register-dayflow-bridge.py" \
  "$GITHUB_WORKSPACE/.github/scripts/test_native_widget_repair.py"
DAYFLOW_SOURCE_DIR="$GITHUB_WORKSPACE/$PROJECT_ROOT" \
  python3 -m unittest discover \
    -s "$GITHUB_WORKSPACE/.github/scripts" \
    -p "test_native_widget_repair.py" -v
# Compile the patched Web assets only after native source regressions pass.
npm run build
npx cap sync android
# Capacitor sync may regenerate MainActivity; register the native plugin only after sync.
PROJECT_ROOT="$GITHUB_WORKSPACE/$PROJECT_ROOT" python3 "$GITHUB_WORKSPACE/.github/scripts/register-dayflow-bridge.py"
grep -q 'registerPlugin(DayflowBridgePlugin.class)' android/app/src/main/java/app/dayflow/android/MainActivity.java
grep -q '.remove(managerId)' android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java
cd android
if [[ -f ./gradlew ]]; then chmod +x ./gradlew; ./gradlew --no-daemon assembleDebug; else gradle --no-daemon assembleDebug; fi
cp app/build/outputs/apk/debug/app-debug.apk "$GITHUB_WORKSPACE/build-output/Yusif-3AMAK-debug.apk"
