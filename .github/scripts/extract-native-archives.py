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
    raw = REPAIR_ARCHIVE.read_bytes()
    if not raw.startswith(b"\x1f\x8b"):
        raw = decode_until(raw, b"\x1f\x8b", "Repair archive")
    payload = gzip_payload(raw)
    required = {
        "patch-native-runtime.py",
        "patch-widget-flow.py",
        "patch-native-reminders.py",
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
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for name, source in found.items():
        if not source.strip():
            raise SystemExit(f"Repair script is empty: {name}.")
        try:
            compile(source.decode("utf-8"), name, "exec")
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise SystemExit(f"Repair script failed syntax validation ({name}): {exc}") from exc
        (SCRIPTS / name).write_bytes(source)
    print("Recovered and syntax-checked all three Android repair scripts.")

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
