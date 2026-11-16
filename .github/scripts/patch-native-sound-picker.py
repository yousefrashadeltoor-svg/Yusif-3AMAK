#!/usr/bin/env python3
"""Use Android's Storage Access Framework and persist ringtone read access."""
from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
PLUGIN = ROOT / "android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java"
BRIDGE = ROOT / "src/lib/nativeBridge.ts"
ALARMS = ROOT / "src/screens/Alarms.tsx"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if old not in source:
        raise SystemExit(f"Sound picker patch could not locate {label}; refusing an unsafe edit")
    return source.replace(old, new, 1)


def patch_plugin() -> None:
    source = PLUGIN.read_text(encoding="utf-8")
    imports = [
        ("import android.app.Activity;", "import android.app.AlarmManager;"),
        ("import com.getcapacitor.ActivityResult;", "import com.getcapacitor.JSArray;"),
        ("import com.getcapacitor.annotation.ActivityCallback;", "import com.getcapacitor.annotation.CapacitorPlugin;"),
    ]
    for line, anchor in imports:
        if line not in source:
            if anchor not in source:
                raise SystemExit(f"DayflowBridgePlugin import anchor not found: {anchor}")
            source = source.replace(anchor, line + "\n" + anchor, 1)

    method = r'''    @PluginMethod public void pickAlarmSound(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("audio/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(call, intent, "pickAlarmSoundResult");
    }

    @ActivityCallback private void pickAlarmSoundResult(PluginCall call, ActivityResult result) {
        if (call == null) return;
        if (result == null || result.getResultCode() != Activity.RESULT_OK) {
            JSObject cancelled = new JSObject();
            cancelled.put("cancelled", true);
            call.resolve(cancelled);
            return;
        }
        Intent data = result.getData();
        Uri uri = data == null ? null : data.getData();
        if (uri == null) {
            call.reject("The selected audio file could not be opened.");
            return;
        }
        int resultFlags = data.getFlags();
        int readFlags = resultFlags & Intent.FLAG_GRANT_READ_URI_PERMISSION;
        if (readFlags == 0 || (resultFlags & Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION) == 0) {
            call.reject("This file provider did not grant persistent read access. Choose a file from a supported device provider.");
            return;
        }
        try {
            getContext().getContentResolver().takePersistableUriPermission(uri, readFlags);
        } catch (SecurityException error) {
            call.reject("Android could not keep access to this audio file. Choose another file.", error);
            return;
        }

        String title = uri.getLastPathSegment();
        Cursor cursor = null;
        try {
            cursor = getContext().getContentResolver().query(
                uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null
            );
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (nameIndex >= 0) title = cursor.getString(nameIndex);
            }
        } catch (RuntimeException ignored) {
            // Some document providers do not expose a display name; retain the URI segment.
        } finally {
            if (cursor != null) cursor.close();
        }
        if (title == null || title.trim().isEmpty()) title = "Selected audio";
        JSObject picked = new JSObject();
        picked.put("uri", uri.toString());
        picked.put("title", title);
        picked.put("cancelled", false);
        call.resolve(picked);
    }

'''
    marker = "    @PluginMethod public void requestOverlayPermission(PluginCall call) {"
    if "@PluginMethod public void pickAlarmSound(PluginCall call)" not in source:
        if marker not in source:
            raise SystemExit("DayflowBridgePlugin overlay method anchor not found")
        source = source.replace(marker, method + marker, 1)
    required = [
        "Intent.ACTION_OPEN_DOCUMENT",
        "Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION",
        "takePersistableUriPermission(uri, readFlags)",
        "@ActivityCallback private void pickAlarmSoundResult(PluginCall call, ActivityResult result)",
        'picked.put("uri", uri.toString());',
    ]
    for token in required:
        if token not in source:
            raise SystemExit("Native audio picker postcondition failed: " + token)
    PLUGIN.write_text(source, encoding="utf-8")


def patch_bridge() -> None:
    source = BRIDGE.read_text(encoding="utf-8")
    source = replace_once(
        source,
        '  getDeviceTones():Promise<{tones:Array<{title:string;uri:string;type:string}>}>;\n',
        '  getDeviceTones():Promise<{tones:Array<{title:string;uri:string;type:string}>}>;\n'
        '  pickAlarmSound():Promise<{uri?:string;title?:string;cancelled?:boolean}>;\n',
        "DayflowNative getDeviceTones interface",
    )
    source = replace_once(
        source,
        '  getDeviceTones:()=>call("getDeviceTones"),\n',
        '  getDeviceTones:()=>call("getDeviceTones"),\n'
        '  pickAlarmSound:()=>call("pickAlarmSound"),\n',
        "nativeBridge getDeviceTones wrapper",
    )
    if 'pickAlarmSound:()=>call("pickAlarmSound")' not in source:
        raise SystemExit("TypeScript native audio picker wrapper was not registered")
    BRIDGE.write_text(source, encoding="utf-8")


def patch_screen() -> None:
    source = ALARMS.read_text(encoding="utf-8")
    state_marker = '  const [file, setFile] = useState<{ name: string; url: string } | null>(null);\n'
    if "const [fileError, setFileError]" not in source:
        source = replace_once(
            source,
            state_marker,
            state_marker + '  const [fileError, setFileError] = useState<string | null>(null);\n',
            "SoundPicker file state",
        )

    start = '        {src === "files" && <div>\n'
    end = '        {src === "downloaded" && <div className="text-center">'
    i = source.find(start)
    j = source.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        if "nativeBridge.pickAlarmSound" not in source:
            raise SystemExit("SoundPicker files-tab block changed; refusing a partial UI patch")
    else:
        replacement = '''        {src === "files" && <div>
          {isAndroidApk() ? <button className="btn btn-soft w-full" onClick={async () => {
            setFileError(null);
            try {
              const picked = await nativeBridge.pickAlarmSound?.();
              if (picked?.uri && !picked.cancelled) onPick({ source: "files", title: picked.title || t("Selected audio", "صوت محدد"), uri: picked.uri });
            } catch (error) {
              setFileError(error instanceof Error ? error.message : t("Could not open the Android audio picker.", "تعذر فتح منتقي الصوت في أندرويد."));
            }
          }}><FolderOpen size={16} />{t("Choose audio from this phone", "اختار صوت من الموبايل")}</button> : <label className="btn btn-soft w-full"><FolderOpen size={16} />{t("Pick an audio file", "اختر ملفًا صوتيًا")}<input type="file" accept="audio/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile({ name: f.name, url: URL.createObjectURL(f) }); }} /></label>}
          {!isAndroidApk() && file && <div className="mt-3 flex items-center gap-2"><button className="btn btn-ghost" onClick={() => { audio.current?.pause(); audio.current = new Audio(file.url); audio.current.play().catch(() => {}); }}><Play size={14} /></button><span className="flex-1 truncate text-sm">{file.name}</span><button className="btn btn-primary" onClick={() => onPick({ source: "files", title: file.name })}>{t("Use", "استخدم")}</button></div>}
          {fileError && <p role="alert" className="mt-2 text-xs text-red-600">{fileError}</p>}
          <p className="mt-3 text-xs muted">{isAndroidApk() ? t("Android keeps secure read access to the selected audio file, so alarms can still use it after the app is closed or the phone restarts.", "أندرويد بيحتفظ بإذن آمن لقراءة ملف الصوت المختار، عشان المنبه يقدر يستخدمه حتى بعد إغلاق التطبيق أو إعادة تشغيل الموبايل.") : t("Choose an audio file from your browser. Temporary previews are available only in this browser session.", "اختار ملف صوتي من المتصفح. المعاينة المؤقتة متاحة في جلسة المتصفح الحالية فقط.")}</p>
        </div>}
'''
        source = source[:i] + replacement + source[j:]
    required = [
        'const [fileError, setFileError] = useState<string | null>(null);',
        "nativeBridge.pickAlarmSound?.()",
        "uri: picked.uri",
        "Android keeps secure read access",
    ]
    for token in required:
        if token not in source:
            raise SystemExit("SoundPicker UI postcondition failed: " + token)
    ALARMS.write_text(source, encoding="utf-8")


def main() -> None:
    for path in (PLUGIN, BRIDGE, ALARMS):
        if not path.is_file():
            raise SystemExit(f"Required DAYFLOW source file is missing: {path}")
    patch_plugin()
    patch_bridge()
    patch_screen()
    print("Verified native SAF alarm-sound picker with persisted URI permission and web fallback.")


if __name__ == "__main__":
    main()
