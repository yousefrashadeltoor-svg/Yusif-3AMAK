#!/usr/bin/env python3
"""Make Android DownloadManager cancellation real and idempotent."""
from __future__ import annotations

from pathlib import Path

plugin = Path("android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java")
if not plugin.is_file():
    raise SystemExit("DayflowBridgePlugin.java is missing; cannot patch download cancellation.")

source = plugin.read_text(encoding="utf-8")
old_enqueue = """            long id = ((DownloadManager)getContext().getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
            JSObject out = new JSObject(); out.put("downloadId", id); out.put("queued", true); call.resolve(out);"""
new_enqueue = """            long id = ((DownloadManager)getContext().getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
            String clientId = call.getString("id", "");
            if (clientId.isEmpty()) clientId = Long.toString(id);
            getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putLong("download_" + clientId, id).apply();
            JSObject out = new JSObject(); out.put("downloadId", id); out.put("id", clientId);
            out.put("queued", true); call.resolve(out);"""
old_cancel = '@PluginMethod public void cancelDownload(PluginCall call) { call.resolve(); }'
new_cancel = """@PluginMethod public void cancelDownload(PluginCall call) {
        String clientId = call.getString("id", "");
        if (clientId.isEmpty()) { call.reject("Download ID is required"); return; }
        android.content.SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long managerId = prefs.getLong("download_" + clientId, -1L);
        if (managerId < 0L) {
            try { managerId = Long.parseLong(clientId); }
            catch (NumberFormatException e) { call.reject("This download is not known to Android DownloadManager"); return; }
        }
        int removed = ((DownloadManager)getContext().getSystemService(Context.DOWNLOAD_SERVICE)).remove(managerId);
        if (removed <= 0) { call.reject("Android could not cancel this download; it may already be complete or unavailable"); return; }
        prefs.edit().remove("download_" + clientId).apply();
        JSObject out = new JSObject(); out.put("cancelled", true); call.resolve(out);
    }"""
if old_enqueue in source:
    source = source.replace(old_enqueue, new_enqueue, 1)
elif new_enqueue not in source:
    raise SystemExit("Expected direct-download enqueue block was not found; refusing an unsafe rewrite.")

if old_cancel in source:
    source = source.replace(old_cancel, new_cancel, 1)
elif new_cancel not in source:
    raise SystemExit("Expected no-op cancelDownload implementation was not found; refusing an unsafe rewrite.")

if ".remove(managerId)" not in source or 'putLong("download_" + clientId, id)' not in source:
    raise SystemExit("Native download cancellation postcondition failed.")

plugin.write_text(source, encoding="utf-8")
print("Patched Android direct-download cancellation to call DownloadManager.remove().")
