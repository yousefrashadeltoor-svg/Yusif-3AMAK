#!/usr/bin/env python3
"""Sanitize the retained Android system-feature archive without dropping core services."""
from __future__ import annotations
import argparse
import base64
import io
import re
import zipfile
from pathlib import Path

START = "    @PluginMethod public void analyzeLink(PluginCall call) {"
END = "    @PluginMethod public void requestNotificationsPermission(PluginCall call) {"
GET_PENDING_SHARE = '    @PluginMethod public void getPendingShare(PluginCall call) { JSObject out = new JSObject(); out.put("text", ""); call.resolve(); }\n'

REMOVE_IMPORTS = (
    "import android.app.DownloadManager;\n",
    "import android.provider.OpenableColumns;\n",
    "import android.webkit.URLUtil;\n",
    "import org.json.JSONArray;\n",
    "import org.json.JSONObject;\n",
    "import java.io.BufferedReader;\n",
    "import java.io.InputStreamReader;\n",
    "import java.net.HttpURLConnection;\n",
    "import java.net.URL;\n",
    "import java.net.URLConnection;\n",
    "import java.net.URLEncoder;\n",
    "import java.util.Locale;\n",
)

def decode_zip(raw: bytes) -> bytes:
    data = raw.strip()
    for _ in range(5):
        if data.startswith(b"PK\x03\x04"):
            return data
        try:
            data = base64.b64decode(data, validate=False)
        except Exception as exc:
            raise RuntimeError(f"Native source archive base64 decoding failed: {exc}") from exc
    raise RuntimeError("Native source archive ZIP signature was not found after decoding.")

def patch_plugin(source: str) -> tuple[str, bool]:
    changed = False
    start_match = re.search(r"@PluginMethod\s+public\s+void\s+analyzeLink\s*\(PluginCall\s+call\)\s*\{", source)
    end_match = re.search(r"@PluginMethod\s+public\s+void\s+requestNotificationsPermission\s*\(PluginCall\s+call\)\s*\{", source)
    if start_match:
        if not end_match or end_match.start() <= start_match.start():
            raise RuntimeError("Native bridge downloader block has no notification-permission boundary.")
        source = source[:start_match.start()] + source[end_match.start():]
        changed = True
    elif "analyzeLink" in source or "directDownload(" in source or "DownloadManager" in source:
        raise RuntimeError("Native bridge contains download logic but its known method boundary changed.")
    pending_pattern = re.compile(r"^\s*@PluginMethod\s+public\s+void\s+getPendingShare\s*\([^)]*\)\s*\{[^}]*\}\s*", re.MULTILINE)
    source, pending_removed = pending_pattern.subn("", source, count=1)
    if pending_removed:
        changed = True
    elif "getPendingShare" in source:
        raise RuntimeError("Native bridge contains shared-URL handoff but its method boundary changed.")

    for imp in REMOVE_IMPORTS:
        if imp in source:
            # Remove only imports that became unused after downloader extraction.
            source = source.replace(imp, "", 1)
            changed = True

    forbidden = ("DownloadManager", "URLUtil", "analyzeLink", "enqueueDownload",
                 "startDownload", "pauseDownload", "cancelDownload", "updateEngines",
                 "openSniffer", "getPendingShare", "directDownload", "HttpURLConnection",
                 "yt-dlp", "gallery-dl", "N_m3u8DL", "aria2c")
    hits = [term for term in forbidden if term in source]
    if hits:
        raise RuntimeError("Downloader references remain in native plugin: " + ", ".join(hits))
    if "scheduleAlarm" not in source or "startCompanionOverlay" not in source or "syncState" not in source:
        raise RuntimeError("Native alarm/overlay/state methods were lost during sanitization.")
    return source, changed

def patch_widget(source: str) -> tuple[str, bool]:
    changed = False
    pattern = re.compile(r'else\s+if\s*\("media"\.equals\(cat\)\)\s*\{[^}]*\}')
    new = 'else if("media".equals(cat)){headline=ar?"مكتبة الوسائط":"Media library";body=ar?"افتح DAYFLOW لعرض ملفاتك الصوتية والمرئية":"Open DAYFLOW to view your audio and video library";footer="";}'
    source, removed = pattern.subn(new, source, count=1)
    if removed:
        changed = True
    elif "Media Hub" in source or "downloads" in source.lower() or "تنزيلاتك" in source:
        raise RuntimeError("Native widget media label changed; refusing an unsafe replacement.")
    if any(term in source for term in ("Media Hub", "downloads", "تنزيلاتك")):
        raise RuntimeError("Downloader wording remains in native launcher widget.")
    return source, changed

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    archive_path = root / "android-native/native-source.zip.b64"
    if not archive_path.is_file():
        raise SystemExit("Native Android source archive is missing.")

    original = archive_path.read_bytes()
    raw_zip = decode_zip(original)
    updates: dict[str, bytes] = {}
    changed = False

    try:
        source_zip = zipfile.ZipFile(io.BytesIO(raw_zip), "r")
        bad = source_zip.testzip()
        if bad:
            raise RuntimeError(f"Native ZIP contains a corrupt entry: {bad}")
        entries = [(info, source_zip.read(info.filename)) for info in source_zip.infolist()]
        source_zip.close()
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Native Android archive is invalid: {exc}") from exc

    found_plugin = found_widget = False
    for info, data in entries:
        name = info.filename
        if name.endswith("/DayflowBridgePlugin.java") or name == "java/app/dayflow/android/DayflowBridgePlugin.java":
            found_plugin = True
            patched, did_change = patch_plugin(data.decode("utf-8"))
            updates[name] = patched.encode("utf-8")
            changed |= did_change
        elif name.endswith("/DayflowWidgetProvider.java") or name == "java/app/dayflow/android/DayflowWidgetProvider.java":
            found_widget = True
            patched, did_change = patch_widget(data.decode("utf-8"))
            updates[name] = patched.encode("utf-8")
            changed |= did_change
        else:
            updates[name] = data

    if not found_plugin or not found_widget:
        raise RuntimeError(f"Native archive is missing required core files (plugin={found_plugin}, widget={found_widget}).")

    if changed:
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
            for info, _ in entries:
                payload = updates[info.filename]
                cloned = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                cloned.compress_type = zipfile.ZIP_DEFLATED
                cloned.external_attr = info.external_attr
                cloned.create_system = info.create_system
                cloned.flag_bits = info.flag_bits
                out.writestr(cloned, payload)
        cleaned = target.getvalue()
        archive_path.write_text(base64.b64encode(cleaned).decode("ascii"), encoding="ascii")
        raw_zip = cleaned

    # Validate the exact encoded object that will be committed and consumed by CI.
    validate = zipfile.ZipFile(io.BytesIO(decode_zip(archive_path.read_bytes())), "r")
    bad = validate.testzip()
    if bad:
        raise RuntimeError(f"Sanitized native archive contains a corrupt entry: {bad}")
    for name in validate.namelist():
        if not name.endswith((".java", ".xml")):
            continue
        body = validate.read(name).decode("utf-8", errors="replace")
        if any(term.lower() in body.lower() for term in (
            "DownloadManager", "yt-dlp", "gallery-dl", "N_m3u8DL", "aria2c",
            "enqueueDownload", "analyzeLink", "startDownload", "pauseDownload",
            "cancelDownload", "updateEngines", "openSniffer", "getPendingShare",
            "directDownload", "Media Hub", "downloads", "تنزيلاتك"
        )):
            raise RuntimeError(f"Downloader residue remains in native archive file: {name}")
    for required in ("AlarmScheduler.java", "AlarmReceiver.java", "BootReceiver.java",
                     "CompanionOverlayService.java", "DayflowWidgetProvider.java",
                     "ReminderScheduler.java", "NativeNotifications.java"):
        if not any(name.endswith(required) for name in validate.namelist()):
            raise RuntimeError(f"Required native system component was lost: {required}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(archive_path.read_bytes())
    print("Native archive validated:", len(validate.namelist()), "entries; changed:", changed)
    print("Preserved alarm, boot recovery, companion overlay, widgets, reminders and notifications.")
    print("Downloader APIs, HTTP extraction helpers and downloader labels are absent.")

if __name__ == "__main__":
    main()
