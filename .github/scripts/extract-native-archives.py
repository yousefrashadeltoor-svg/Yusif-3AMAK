#!/usr/bin/env python3
"""Validate and recover the bundled DAYFLOW Android source archives for CI."""
from __future__ import annotations

import base64
import gzip
import io
import pathlib
import struct
import tarfile
import zipfile
import zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = REPO / ".github" / "scripts"
NATIVE_ARCHIVE = REPO / "android-native" / "native-source.zip.b64"
REPAIR_ARCHIVE = REPO / "android-native" / "repair-scripts.tar.gz.b64"
NATIVE_OUTPUT = pathlib.Path("/tmp/dayflow-native.zip")

def decode_until(data: bytes, signature: bytes, label: str) -> bytes:
    data = data.strip()
    for _ in range(4):
        if data.startswith(signature):
            return data
        try:
            data = base64.b64decode(data, validate=False)
        except Exception as exc:
            raise SystemExit(f"{label}: base64 decoding failed: {exc}") from exc
    raise SystemExit(f"{label}: expected archive signature was not found after decoding.")

def gzip_payload(data: bytes) -> bytes:
    try:
        return gzip.decompress(data)
    except (OSError, EOFError, zlib.error):
        # The checked-in gzip has a damaged checksum/size trailer. Recover only
        # when the raw DEFLATE stream is complete and the resulting tar is valid.
        if len(data) < 18 or data[2] != 8:
            raise SystemExit("Repair archive is not a complete gzip stream.")
        flags = data[3]
        if flags & 0xE0:
            raise SystemExit("Repair archive uses unsupported gzip header flags.")
        offset = 10
        if flags & 4:
            if len(data) < offset + 2:
                raise SystemExit("Repair archive has a truncated gzip extra header.")
            extra_len = struct.unpack("<H", data[offset:offset + 2])[0]
            offset += 2 + extra_len
        for flag in (8, 16):
            if flags & flag:
                end = data.find(b"\0", offset)
                if end < 0:
                    raise SystemExit("Repair archive has a truncated gzip header field.")
                offset = end + 1
        if flags & 2:
            offset += 2
        if len(data) < offset + 8:
            raise SystemExit("Repair archive is truncated.")
        inflater = zlib.decompressobj(-zlib.MAX_WBITS)
        try:
            payload = inflater.decompress(data[offset:-8]) + inflater.flush()
        except zlib.error as exc:
            raise SystemExit(f"Repair archive DEFLATE data is corrupt: {exc}") from exc
        if not inflater.eof:
            raise SystemExit("Repair archive DEFLATE stream ended unexpectedly.")
        return payload

def extract_repair_scripts() -> None:
    # The source package is split into ordered text chunks so GitHub stores it
    # as UTF-8 and each part can be independently inspected and recovered.
    parts = sorted(
        (REPO / "android-native").glob("repair-scripts-v2.part*.b64"),
        key=lambda p: int(p.stem.rsplit("part", 1)[1]),
    )
    if not parts:
        raise SystemExit("Repair source archive parts are missing.")
    numbers = [int(p.stem.rsplit("part", 1)[1]) for p in parts]
    expected = list(range(1, len(parts) + 1))
    if numbers != expected:
        raise SystemExit(f"Repair source archive parts are not contiguous: {numbers}")
    encoded = b"".join(p.read_bytes().strip() for p in parts)
    if len(encoded) % 4:
        raise SystemExit("Repair source archive has an incomplete base64 sequence.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"Repair source archive base64 is invalid: {exc}") from exc
    payload = gzip_payload(raw)
    required = {
        "patch-native-runtime.py",
        "patch-widget-flow.py",
        "patch-native-reminders.py",
        "test_native_widget_repair.py",
    }
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            name = pathlib.PurePosixPath(member.name)
            if not member.isfile() or name.is_absolute() or ".." in name.parts:
                continue
            if name.name in required:
                if name.name in found:
                    raise SystemExit(f"Repair archive contains duplicate {name.name}.")
                stream = archive.extractfile(member)
                if stream is None:
                    raise SystemExit(f"Repair archive cannot read {name.name}.")
                found[name.name] = stream.read()
    missing = required - found.keys()
    if missing:
        raise SystemExit("Repair archive is missing: " + ", ".join(sorted(missing)))
    # The packed patchers are applied in sequence, then tested again against the
    # resulting combined source tree. Keep each integration idempotent when a
    # later patcher has already appended its own sync hook.
    widget_legacy = """    if new_sync not in p:
        matched = next((old for old in old_sync_variants if old in p), None)
        if matched is None: raise RuntimeError("Native widget sync method changed; refusing to overwrite unknown plugin behavior")
        p = p.replace(matched, new_sync, 1)
"""
    widget_safe = """    signature = '@PluginMethod public void syncState(PluginCall call) {'
    sync_start = p.find(signature)
    sync_end = p.find('\\n    }', sync_start) if sync_start >= 0 else -1
    if sync_start < 0 or sync_end < 0:
        raise RuntimeError("Native syncState method was not found; refusing to alter unknown plugin behavior")
    sync_method = p[sync_start:sync_end]
    widget_refresh = 'DayflowWidgetProvider.refreshAll(getContext());'
    if widget_refresh not in sync_method:
        matched = next((old for old in old_sync_variants if old in p), None)
        if matched is not None:
            p = p.replace(matched, new_sync, 1)
        else:
            resolve_marker = '        call.resolve();'
            if resolve_marker not in sync_method:
                raise RuntimeError("Native syncState method has no expected resolve point; refusing to alter unknown plugin behavior")
            sync_method = sync_method.replace(
                resolve_marker,
                '        ' + widget_refresh + "\\n" + resolve_marker,
                1,
            )
            p = p[:sync_start] + sync_method + p[sync_end:]
"""
    reminder_legacy = '    p = replace_once(p, old_sync, new_sync, "app state to native reminder scheduler")\n'
    reminder_safe = """    signature = '@PluginMethod public void syncState(PluginCall call) {'
    sync_start = p.find(signature)
    sync_end = p.find('\\n    }', sync_start) if sync_start >= 0 else -1
    if sync_start < 0 or sync_end < 0:
        raise RuntimeError("Native syncState method was not found; refusing to alter unknown plugin behavior")
    sync_method = p[sync_start:sync_end]
    reminder_sync = 'ReminderScheduler.syncFromState(getContext(), json);'
    if reminder_sync not in sync_method:
        if old_sync in p:
            p = p.replace(old_sync, new_sync, 1)
        else:
            resolve_marker = '        call.resolve();'
            if resolve_marker not in sync_method:
                raise RuntimeError("Native syncState method has no expected resolve point; refusing to alter unknown plugin behavior")
            sync_method = sync_method.replace(
                resolve_marker,
                '        ' + reminder_sync + "\\n" + resolve_marker,
                1,
            )
            p = p[:sync_start] + sync_method + p[sync_end:]
"""
    for script_name, old_block, new_block in (
        ("patch-widget-flow.py", widget_legacy, widget_safe),
        ("patch-native-reminders.py", reminder_legacy, reminder_safe),
    ):
        script_text = found[script_name].decode("utf-8")
        if old_block in script_text:
            script_text = script_text.replace(old_block, new_block, 1)
        elif new_block not in script_text:
            raise SystemExit(f"{script_name}: expected native sync patch block was not found; refusing an unsafe archive rewrite.")
        found[script_name] = script_text.encode("utf-8")

    # The overlay patcher generates the Java method after patch-app-features.py
    # has run. Correct the generated source template here so the native plugin
    # explicitly unboxes Capacitor's Double before placing a float extra.
    runtime = found["patch-native-runtime.py"].decode("utf-8")
    for field in ("size", "opacity"):
        invalid = f'intent.putExtra("{field}", (float)call.getDouble("{field}", 1.0));'
        valid = f'intent.putExtra("{field}", call.getDouble("{field}", 1.0).floatValue());'
        if invalid in runtime:
            runtime = runtime.replace(invalid, valid, 1)
        elif valid not in runtime:
            raise SystemExit(f"patch-native-runtime.py: expected {field} overlay extra was not found; refusing an unsafe archive rewrite.")
    found["patch-native-runtime.py"] = runtime.encode("utf-8")

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for name, source in found.items():
        if not source.strip():
            raise SystemExit(f"Repair script is empty: {name}.")
        try:
            compile(source.decode("utf-8"), name, "exec")
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise SystemExit(f"Repair script failed syntax validation ({name}): {exc}") from exc
        (SCRIPTS / name).write_bytes(source)
    print("Recovered and syntax-checked all three Android repair scripts and their regression tests.")

def validate_native_source() -> None:
    raw = decode_until(NATIVE_ARCHIVE.read_bytes(), b"PK\x03\x04", "Native source ZIP")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            corrupt = archive.testzip()
            if corrupt:
                raise SystemExit(f"Native source ZIP contains a corrupt entry: {corrupt}")
            names = set(archive.namelist())
            required = {
                "java/app/dayflow/android/DayflowBridgePlugin.java",
                "res/layout/dayflow_widget.xml",
                "res/xml/dayflow_widget_info.xml",
            }
            missing = required - names
            if missing:
                raise SystemExit("Native source ZIP is missing: " + ", ".join(sorted(missing)))
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Native source ZIP is invalid: {exc}") from exc
    NATIVE_OUTPUT.write_bytes(raw)
    print("Validated native source ZIP and required Android components.")

if __name__ == "__main__":
    extract_repair_scripts()
    validate_native_source()
