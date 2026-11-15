#!/usr/bin/env python3
"""Remove downloader-only code from the retained Android repair-script archive.

Only two obsolete pieces are changed in patch-widget-flow.py:
1) the Media Hub/downloads label in the generated local-media widget text;
2) the old analyzeLink method boundary used to delimit pinWidget replacement.
Widget pinning, widget selection, state sync, reminders and overlay logic remain.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import io
import os
import pathlib
import struct
import tarfile
import zlib

OLD_BOUNDARY = "end = p.find('    @PluginMethod public void analyzeLink(PluginCall call) {', start)"
NEW_BOUNDARY = "end = p.find('    @PluginMethod public void requestNotificationsPermission(PluginCall call) {', start)"
OLD_MEDIA = 'else if("media".equals(cat)){headline=ar?"مركز الوسائط":"Media Hub";body=ar?"افتح DAYFLOW لمتابعة ملفاتك وتنزيلاتك":"Open DAYFLOW to view media and downloads";footer="";}'
NEW_MEDIA = 'else if("media".equals(cat)){headline=ar?"مكتبة الوسائط":"Media library";body=ar?"افتح DAYFLOW لعرض ملفاتك الصوتية والمرئية":"Open DAYFLOW to view your audio and video library";footer="";}'
FORBIDDEN = (
    "DownloadManager", "URLUtil", "yt-dlp", "gallery-dl", "N_m3u8DL", "aria2c",
    "enqueueDownload", "analyzeLink", "startDownload", "pauseDownload",
    "cancelDownload", "updateEngines", "openSniffer", "getPendingShare",
    "directDownload", "downloads.ts", "Downloads.tsx", "MediaHub.tsx",
    "#/downloads", "Active downloads", "Download history", "Paste-link tile",
    "Media Hub", "افتح DAYFLOW لمتابعة ملفاتك وتنزيلاتك",
)

def gunzip_recover(raw: bytes) -> bytes:
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

    archive_dir = args.repo_root / "android-native"
    parts = sorted(archive_dir.glob("repair-scripts-v2.part*.b64"),
                   key=lambda p: int(p.stem.rsplit("part", 1)[1]))
    numbers = [int(p.stem.rsplit("part", 1)[1]) for p in parts]
    if not parts or numbers != list(range(1, len(parts) + 1)):
        raise RuntimeError(f"Repair archive chunks missing or out of order: {numbers}")
    encoded = b"".join(p.read_bytes().strip() for p in parts)
    if len(encoded) % 4:
        raise RuntimeError("Repair archive chunks contain an incomplete base64 sequence.")
    raw = base64.b64decode(encoded, validate=True)
    tar_payload = gunzip_recover(raw)

    entries: list[tuple[tarfile.TarInfo, bytes]] = []
    widget_changed = False
    with tarfile.open(fileobj=io.BytesIO(tar_payload), mode="r:") as archive:
        for info in archive.getmembers():
            if info.isfile():
                stream = archive.extractfile(info)
                if stream is None:
                    raise RuntimeError(f"Could not read repair member {info.name}")
                payload = stream.read()
                if pathlib.PurePosixPath(info.name).name == "patch-widget-flow.py":
                    text = payload.decode("utf-8")
                    if OLD_BOUNDARY in text:
                        text = text.replace(OLD_BOUNDARY, NEW_BOUNDARY, 1)
                        widget_changed = True
                    elif NEW_BOUNDARY not in text:
                        raise RuntimeError("Widget patcher has no recognized native plugin boundary.")
                    if OLD_MEDIA in text:
                        text = text.replace(OLD_MEDIA, NEW_MEDIA, 1)
                        widget_changed = True
                    elif NEW_MEDIA not in text:
                        raise RuntimeError("Widget patcher media label changed; refusing an unsafe replacement.")
                    payload = text.encode("utf-8")
                entries.append((info, payload))
            else:
                entries.append((info, b""))

    names = {pathlib.PurePosixPath(info.name).name for info, _ in entries if info.isfile()}
    required = {"patch-native-runtime.py", "patch-widget-flow.py",
                "patch-native-reminders.py", "test_native_widget_repair.py"}
    if required - names:
        raise RuntimeError("Repair archive missing required members: " + ", ".join(sorted(required - names)))

    # Repack with intact member paths and permissions.
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:") as output_tar:
        for info, payload in entries:
            item = tarfile.TarInfo(info.name)
            item.mode = info.mode
            item.uid = info.uid
            item.gid = info.gid
            item.uname = info.uname
            item.gname = info.gname
            item.mtime = info.mtime
            item.type = info.type
            item.linkname = info.linkname
            item.pax_headers = dict(info.pax_headers)
            item.size = len(payload) if info.isfile() else 0
            output_tar.addfile(item, io.BytesIO(payload) if info.isfile() else None)
    new_gzip = gzip.compress(tar_buffer.getvalue(), compresslevel=9, mtime=0)
    new_encoded = base64.b64encode(new_gzip).decode("ascii")

    # Preserve the six-part format and filenames consumed by extract-native-archives.py.
    chunk_count = len(parts)
    chunk_size = (len(new_encoded) + chunk_count - 1) // chunk_count
    chunks = [new_encoded[i * chunk_size:(i + 1) * chunk_size] for i in range(chunk_count)]
    if "".join(chunks) != new_encoded or any(not chunk for chunk in chunks):
        raise RuntimeError("Failed to split the sanitized repair archive into contiguous chunks.")
    for part, chunk in zip(parts, chunks):
        part.write_text(chunk, encoding="ascii")

    # Scan all Python files in the new archive, not just the widget script.
    report_lines = [
        "status: passed" if widget_changed or NEW_BOUNDARY in new_encoded else "status: already-clean",
        f"member-count: {len(entries)}",
        f"archive-sha256: {hashlib.sha256(new_gzip).hexdigest()}",
        f"widget-patcher-updated: {str(widget_changed).lower()}",
    ]
    residue = []
    with tarfile.open(fileobj=io.BytesIO(tar_buffer.getvalue()), mode="r:") as check:
        for member in check.getmembers():
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            stream = check.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Could not verify {member.name}")
            text = stream.read().decode("utf-8", errors="strict")
            for line_num, line in enumerate(text.splitlines(), 1):
                for token in FORBIDDEN:
                    if token.casefold() in line.casefold():
                        residue.append(f"{member.name}:{line_num}: {token}")
    if residue:
        raise RuntimeError("Downloader residue remains in repair scripts:\n" + "\n".join(residue[:60]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a", encoding="utf-8") as output:
        output.write(f"changed={'true' if widget_changed else 'false'}\n")
    print("\n".join(report_lines))
    print("No downloader APIs, routes, engines or downloader widget labels remain in the retained repair archive.")

if __name__ == "__main__":
    main()
