#!/usr/bin/env python3
"""Audit the retained Android patch archive for obsolete downloader tooling.

This is a read-only inspection: it never extracts or applies patch scripts.
The scripts that remain are retained only for Android alarms, reminders,
widgets and the floating companion.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import io
import pathlib
import struct
import tarfile
import zlib

EXPECTED = {
    "patch-native-runtime.py",
    "patch-widget-flow.py",
    "patch-native-reminders.py",
    "test_native_widget_repair.py",
}
FORBIDDEN = (
    "DownloadManager", "URLUtil", "yt-dlp", "gallery-dl", "N_m3u8DL", "aria2c",
    "enqueueDownload", "analyzeLink", "startDownload", "pauseDownload",
    "cancelDownload", "updateEngines", "openSniffer", "getPendingShare",
    "directDownload", "downloads.ts", "Downloads.tsx", "MediaHub.tsx",
    "#/downloads", "Active downloads", "Download history", "Paste-link tile",
    "Media Hub",
)

def unpack_gzip(raw: bytes) -> bytes:
    try:
        return gzip.decompress(raw)
    except (OSError, EOFError, zlib.error):
        if len(raw) < 18 or raw[2] != 8:
            raise RuntimeError("Repair archive is not a complete gzip stream.")
        flags = raw[3]
        if flags & 0xE0:
            raise RuntimeError("Repair archive uses unsupported gzip header flags.")
        offset = 10
        if flags & 4:
            if len(raw) < offset + 2:
                raise RuntimeError("Repair archive has a truncated extra header.")
            extra_len = struct.unpack("<H", raw[offset:offset + 2])[0]
            offset += 2 + extra_len
        for flag in (8, 16):
            if flags & flag:
                end = raw.find(b"\0", offset)
                if end < 0:
                    raise RuntimeError("Repair archive has a truncated optional header field.")
                offset = end + 1
        if flags & 2:
            offset += 2
        if len(raw) < offset + 8:
            raise RuntimeError("Repair archive is truncated.")
        inflater = zlib.decompressobj(-zlib.MAX_WBITS)
        payload = inflater.decompress(raw[offset:-8]) + inflater.flush()
        if not inflater.eof:
            raise RuntimeError("Repair archive DEFLATE stream ended unexpectedly.")
        return payload

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=pathlib.Path, required=True)
    ap.add_argument("--report", type=pathlib.Path, required=True)
    args = ap.parse_args()
    folder = args.repo_root / "android-native"
    parts = sorted(folder.glob("repair-scripts-v2.part*.b64"),
                   key=lambda p: int(p.stem.rsplit("part", 1)[1]))
    numbers = [int(p.stem.rsplit("part", 1)[1]) for p in parts]
    if numbers != list(range(1, len(parts) + 1)) or not parts:
        raise RuntimeError(f"Repair archive chunks are missing or out of order: {numbers}")
    encoded = b"".join(p.read_bytes().strip() for p in parts)
    if len(encoded) % 4:
        raise RuntimeError("Repair archive chunks contain an incomplete base64 sequence.")
    raw = base64.b64decode(encoded, validate=True)
    payload = unpack_gzip(raw)

    found = {}
    forbidden_hits = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = pathlib.PurePosixPath(member.name).name
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Cannot read archive member {member.name}")
            data = stream.read()
            if name.endswith(".py"):
                text = data.decode("utf-8", errors="strict")
                if name in EXPECTED:
                    found[name] = hashlib.sha256(data).hexdigest()
                for token in FORBIDDEN:
                    if token.casefold() in text.casefold():
                        forbidden_hits.append((member.name, token))
    missing = EXPECTED - found.keys()
    if missing:
        raise RuntimeError("Retained Android patch archive is missing: " + ", ".join(sorted(missing)))
    if forbidden_hits:
        formatted = "\n".join(f"{path}: {token}" for path, token in forbidden_hits)
        raise RuntimeError("Downloader-specific patch content remains in retained repair archive:\n" + formatted)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["status: passed", f"archive-sha256: {hashlib.sha256(raw).hexdigest()}",
             f"python-patchers: {len(found)}"]
    lines.extend(f"{name}: {digest}" for name, digest in sorted(found.items()))
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
