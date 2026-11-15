#!/usr/bin/env python3
"""Remove DAYFLOW's downloader-only product surface from an extracted source tree.

Generic file save/export (backups, QR output, converted images) is intentionally
preserved. User-owned alarm audio previously labelled "downloaded" is migrated
as an existing local-file reference rather than being deleted.
"""
from __future__ import annotations
import argparse
from pathlib import Path


def read(root: Path, rel: str) -> str:
    p = root / rel
    if not p.exists():
        raise FileNotFoundError(f"Required source file missing: {rel}")
    return p.read_text(encoding="utf-8")


def write(root: Path, rel: str, content: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(root: Path, rel: str, old: str, new: str, label: str) -> None:
    s = read(root, rel)
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected one exact match in {rel}, found {n}")
    write(root, rel, s.replace(old, new, 1))


def remove_block(root: Path, rel: str, start: str, end: str, label: str) -> None:
    s = read(root, rel)
    if s.count(start) != 1:
        raise RuntimeError(f"{label}: expected one start marker in {rel}")
    a = s.index(start)
    b = s.find(end, a + len(start))
    if b < 0:
        raise RuntimeError(f"{label}: end marker missing in {rel}")
    b += len(end)
    write(root, rel, s[:a] + s[b:])


def remove_file(root: Path, rel: str) -> None:
    p = root / rel
    if not p.exists():
        raise RuntimeError(f"Expected downloader-only file missing: {rel}")
    p.unlink()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    args = ap.parse_args()
    root = args.source_root.resolve()

    # Keep byte formatting shared by unrelated file-import, QR, and model UI.
    write(root, "src/lib/format.ts", '''/** Human-readable byte formatting shared by non-downloader file features. */
export const fmtBytes = (b: number) => (b <= 0 ? "—" : b < 1e6 ? (b / 1e3).toFixed(0) + " KB" : b < 1e9 ? (b / 1e6).toFixed(1) + " MB" : (b / 1e9).toFixed(2) + " GB");
''')

    # Main navigation, deep links, quick-create and system-share-to-download handoff.
    replace_once(root, "src/App.tsx", "Timer, Link2, Hourglass", "Timer, Hourglass", "remove paste-link icon")
    replace_once(root, "src/App.tsx", ", Sparkles, Bot, Download }", ", Sparkles, Bot }", "remove downloader tab icon")
    replace_once(root, "src/App.tsx", 'import { Downloads } from "./screens/Downloads";\n', "", "remove Downloads screen import")
    replace_once(root, "src/App.tsx", 'import { initShare } from "./lib/share";\n', "", "remove downloader share intent")
    replace_once(root, "src/App.tsx", 'type Tab = "today" | "calendar" | "alarms" | "tools" | "me" | "ai" | "downloads";', 'type Tab = "today" | "calendar" | "alarms" | "tools" | "me" | "ai";', "remove downloads route type")
    replace_once(root, "src/App.tsx", '"today", "calendar", "alarms", "tools", "me", "ai", "downloads"', '"today", "calendar", "alarms", "tools", "me", "ai"', "remove downloads route parser")
    replace_once(root, "src/App.tsx", '  useEffect(() => initShare(() => { history.pushState(null, "", "#/downloads"); setRoute({ tab: "downloads" }); }), []);\n', "", "remove URL share-to-downloader effect")
    replace_once(root, "src/App.tsx", ', ["downloads", Download, t("Download", "التحميل")]', "", "remove downloads navigation item")
    replace_once(root, "src/App.tsx", '        {route.tab === "downloads" && <Downloads go={go} />}\n', "", "remove downloads route renderer")
    replace_once(root, "src/App.tsx", ', [Link2, t("Paste a link", "الصق رابطًا"), () => { close(); go("tools", "media"); }]', "", "remove paste-link quick action")

    # Today screen downloader promotion.
    replace_once(root, "src/screens/Today.tsx", "AlarmClock, Check, Download, Droplet", "AlarmClock, Check, Droplet", "remove downloader icon")
    remove_block(root, "src/screens/Today.tsx", '      <Card className="mb-3 flex items-center gap-3 p-3" onClick={() => go("downloads")}>', "</Card>", "remove Today downloader card")

    # Tools catalog: retain unrelated image conversion and file-size labels.
    replace_once(root, "src/screens/Tools.tsx", "StickyNote, Link2, Hourglass", "StickyNote, Hourglass", "remove media link icon")
    replace_once(root, "src/screens/Tools.tsx", 'import { fmtBytes } from "../lib/media";', 'import { fmtBytes } from "../lib/format";', "preserve shared byte formatter")
    replace_once(root, "src/screens/Tools.tsx", 'import { MediaHub } from "./MediaHub";\n', "", "remove Media Hub import")
    replace_once(root, "src/screens/Tools.tsx", ', ["media", Link2, "Media Hub", "مركز الوسائط"]', "", "remove Media Hub tool entry")
    replace_once(root, "src/screens/Tools.tsx", '    if (sub === "media") return <MediaHub onBack={back} />;\n', "", "remove Media Hub route")

    # Shared byte helper remains available to non-downloader screens.
    for rel in ("src/screens/AI.tsx", "src/screens/QRShareViewer.tsx", "src/screens/QRStudio.tsx", "src/components/ModelViewer.tsx"):
        replace_once(root, rel, 'from "../lib/media"', 'from "../lib/format"', "redirect shared byte formatter")

    # Floating companion: remove link detection/paste tab while keeping AI/tasks/alarms/capture.
    replace_once(root, "src/components/Companion.tsx", ", AlarmClock, Link2, Zap", ", AlarmClock, Zap", "remove companion link icon")
    replace_once(root, "src/components/Companion.tsx", 'import { normalizeUrl } from "../lib/media";\n', "", "remove companion URL parser")
    replace_once(root, "src/components/Companion.tsx", 'bubble.action === "habits" ? "habits" : bubble.action === "media" ? "media" : undefined', 'bubble.action === "habits" ? "habits" : undefined', "remove companion Media Hub action")
    replace_once(root, "src/components/Companion.tsx", 'const [tab, setTab] = useState<"ai" | "tasks" | "alarms" | "media" | "capture" | "more">("ai");', 'const [tab, setTab] = useState<"ai" | "tasks" | "alarms" | "capture" | "more">("ai");', "remove companion media state")
    replace_once(root, "src/components/Companion.tsx", ', ["media", Link2, t("Media", "وسائط")]', "", "remove companion media tab")
    replace_once(root, "src/components/Companion.tsx", '  const parsed = tab === "media" && txt ? normalizeUrl(txt) : null;\n', "", "remove companion URL parsing")
    remove_block(root, "src/components/Companion.tsx", '          {tab === "media" && <>', '</>}', "remove companion paste-link panel")

    # Remove downloader widget templates/actions and corresponding three catalog items.
    replace_once(root, "src/lib/widgets.ts", ' | "download"', "", "remove downloader widget archetype")
    replace_once(root, "src/lib/widgets.ts", 'media: [["Active downloads", "التنزيلات النشطة", "download", 1], ["Paste-link tile", "بلاطة لصق الرابط", "quick", 1], ["Download history", "سجل التنزيلات", "list", 0], ', 'media: [', "remove downloader widget definitions")
    replace_once(root, "src/components/WidgetRenderer.tsx", "Check, Plus, Mic, Link2, Droplet", "Check, Plus, Mic, Droplet", "remove downloader widget icon")
    remove_block(root, "src/components/WidgetRenderer.tsx", '      case "download": return ', '\n', "remove downloader widget renderer")
    replace_once(root, "src/components/WidgetRenderer.tsx", 'const acts = def.id.includes("paste") ? [[Link2, L("Paste", "لصق")]] : def.id.includes("voice") ? [[Mic, L("Record", "تسجيل")]] : [[Plus, L("Task", "مهمة")], [AlarmClock, L("Alarm", "منبه")], [Droplet, L("Water", "ماء")], [Timer, L("Focus", "تركيز")], [StickyNote, L("Note", "ملاحظة")], [Link2, L("Link", "رابط")]];', 'const acts = def.id.includes("voice") ? [[Mic, L("Record", "تسجيل")]] : [[Plus, L("Task", "مهمة")], [AlarmClock, L("Alarm", "منبه")], [Droplet, L("Water", "ماء")], [Timer, L("Focus", "تركيز")], [StickyNote, L("Note", "ملاحظة")]];', "remove downloader quick-widget actions")

    # Remove downloader settings/sound source and its UI; keep local-file picker.
    replace_once(root, "src/lib/store.ts", 'export type SoundSource = "library" | "device" | "files" | "downloaded";', 'export type SoundSource = "library" | "device" | "files";', "remove downloaded alarm sound source")
    replace_once(root, "src/lib/store.ts", '  tasbih: number; khatma: number; clipboardWatch: boolean; mediaNoticeSeen: boolean;', '  tasbih: number; khatma: number;', "remove downloader settings state")
    replace_once(root, "src/lib/store.ts", '      tasbih: 0, khatma: 0, clipboardWatch: false, mediaNoticeSeen: false,', '      tasbih: 0, khatma: 0,', "remove downloader settings defaults")
    replace_once(root, "src/lib/store.ts", '    { name: "dayflow-v2", version: 3, migrate: (state) => state as S, storage:', '    { name: "dayflow-v2", version: 4, migrate: (state) => { const old = state as S & { clipboardWatch?: boolean; mediaNoticeSeen?: boolean; cityIndex?: number }; const { clipboardWatch: _clipboardWatch, mediaNoticeSeen: _mediaNoticeSeen, ...safe } = old; return { ...safe, alarms: (safe.alarms || []).map((a) => (a.sound as { source: string }).source === "downloaded" ? { ...a, sound: { ...a.sound, source: "files" as SoundSource } } : a), placed: (safe.placed || []).filter((w) => !["media-active-downloads", "media-paste-link-tile", "media-download-history"].includes(w.designId)), hour12: true, cityIndex: old.cityIndex === 0 ? 10 : old.cityIndex ?? 10 } as S; }, storage:', "migrate existing downloaded alarm tones as local-file refs")

    # Sound picker no longer advertises downloaded audio; preserve user file references via migration.
    replace_once(root, "src/screens/Alarms.tsx", "Plus, Trash2, Bell, Smartphone, FolderOpen, Download, Library", "Plus, Trash2, Bell, Smartphone, FolderOpen, Library", "remove downloaded sound icon")
    replace_once(root, "src/screens/Alarms.tsx", ', { id: "downloaded", label: t("Downloaded", "المنزّلة") }', "", "remove downloaded sound picker option")
    remove_block(root, "src/screens/Alarms.tsx", '        {src === "downloaded" && <div className="text-center">', '</div>}', "remove downloaded sound picker panel")

    # Remove link-detection setting and downloader-specific references from settings/ledger.
    replace_once(root, "src/screens/Me.tsx", '        <Row title={t("Downloaded", "المنزّلة")} hint={t("From the Media Hub, with a trimmer", "من مركز الوسائط مع أداة قص")} />\n', "", "remove downloaded sound library row")
    replace_once(root, "src/screens/Me.tsx", '    { g: t("Media Hub", "مركز الوسائط"), k: "clip", title: t("Detect copied links", "اكتشاف الروابط المنسوخة"), hint: t("Only while the app is open", "فقط أثناء فتح التطبيق"), right: <Toggle on={s.clipboardWatch} onChange={(v) => s.set({ clipboardWatch: v })} label="clipboard" /> },\n', "", "remove clipboard URL detector setting")
    replace_once(root, "src/screens/Me.tsx", '    ["Media Hub real previews (oEmbed) + real direct download", "Built", "YouTube title fetched; CC0 file 1,128,375 B fetched"],\n', "", "remove downloader from feature ledger")
    replace_once(root, "src/screens/Me.tsx", '    ["Native alarm engine, device tones, native widgets, Filament companion, download engine", "Unverified", "No Android toolchain or APK in this environment"],', '    ["Native alarm engine, device tones, native widgets, Filament companion", "Unverified", "No Android toolchain or APK in this environment"],', "remove download engine ledger claim")

    # Remove assistant routing/intents that point to deleted screens.
    replace_once(root, "src/lib/agent.ts", 'const routes = ["today", "calendar", "alarms", "tools", "me", "ai", "downloads"];', 'const routes = ["today", "calendar", "alarms", "tools", "me", "ai"];', "remove AI downloads route")
    replace_once(root, "src/lib/store.ts", '["today", "calendar", "alarms", "tools", "me", "ai", "downloads"]', '["today", "calendar", "alarms", "tools", "me", "ai"]', "remove action downloads route")
    replace_once(root, "src/lib/soul.ts", 'action?: "alarms" | "tasks" | "habits" | "media" | "ai" | "settings"', 'action?: "alarms" | "tasks" | "habits" | "ai" | "settings"', "remove media action type")
    replace_once(root, "src/lib/soul.ts", '  if (/(تحميل|فيديو|رابط|media|download|لينك)/.test(q)) return { text: ar ? "افتح مركز الوسائط والصق الرابط، هيجيبلك اسم الفيديو وصورته والمدة أحجام الصيغ. للتحميل الفعلي محتاج نسخة أندرويد." : "Open the Media Hub and paste the link.", mood: "idle", actions: [act("open", { tab: "tools", sub: "media" })] };\n', "", "remove assistant downloader recommendation")

    # Native bridge: strip URL-analysis, media downloader and shared-URL handoff APIs.
    native = "android/app/src/main/java/app/dayflow/android/DayflowBridgePlugin.java"
    if (root / native).exists():
        remove_block(root, native, '    @PluginMethod public void analyzeLink(PluginCall call) {', '    @PluginMethod public void requestNotificationsPermission(PluginCall call) {', "remove native URL extraction/download methods")
        replace_once(root, native, '    @PluginMethod public void getPendingShare(PluginCall call) { JSObject out = new JSObject(); out.put("text", ""); call.resolve(out); }\n', "", "remove native shared-URL handoff")
        for imp in (
            "import android.app.DownloadManager;\n", "import android.webkit.URLUtil;\n",
            "import org.json.JSONArray;\n", "import java.io.BufferedReader;\n",
            "import java.io.InputStreamReader;\n", "import java.net.HttpURLConnection;\n",
            "import java.net.URL;\n", "import java.util.Locale;\n",
        ):
            s = read(root, native)
            if imp in s:
                write(root, native, s.replace(imp, "", 1))
    
    else:
        print("Generated Android bridge not present in the original source archive; native platform archive remains untouched for later Compose service migration.")
    # TypeScript side of the native bridge must no longer expose downloader methods.
    # Source archive uses the formatted bridge layout; remove each downloader-only
    # declaration/wrapper by property name, independent of whitespace formatting.
    import re
    bridge = "src/lib/nativeBridge.ts"
    s = read(root, bridge)
    names = ("enqueueDownload", "analyzeLink", "startDownload", "pauseDownload",
             "cancelDownload", "updateEngines", "openSniffer", "getPendingShare")
    for name in names:
        pattern = re.compile(r"^\\s*" + re.escape(name) + r"\\s*(?:\\(|:).*?$", re.MULTILINE)
        s, removed = pattern.subn("", s)
        if removed < 1:
            raise RuntimeError(f"Native bridge downloader declaration/wrapper missing: {name}")
    write(root, bridge, s)

    # Update native local-media widget text without removing audio/video/storage widgets.
    replace_once(root, "android/app/src/main/java/app/dayflow/android/DayflowWidgetProvider.java",
        'body=ar?"افتح DAYFLOW لمتابعة ملفاتك وتنزيلاتك":"Open DAYFLOW to view media and downloads";',
        'body=ar?"افتح DAYFLOW لمتابعة ملفاتك الصوتية والمرئية":"Open DAYFLOW to view your audio and video library";',
        "remove downloader wording from launcher widget")
    replace_once(root, "src/lib/widgets.ts", '{ id: "media", en: "Media Hub", ar: "مركز الوسائط" }', '{ id: "media", en: "Media library", ar: "مكتبة الوسائط" }', "rename retained local-media widget category")
    replace_once(root, "src/lib/ai.ts", 'and a Media Hub that fetches public previews & direct files in browser (native yt-dlp/FFmpeg engine in the Android project).', 'and local media-library references for audio, video and storage summaries.', "remove downloader claims from AI context")
    replace_once(root, "android/app/src/main/java/app/dayflow/android/DayflowWidgetProvider.java", 'headline=ar?"مركز الوسائط":"Media Hub";', 'headline=ar?"مكتبة الوسائط":"Media library";', "rename retained native media-library widget")

    # Delete downloader-only screens, engines and URL share plumbing. Generic fmtBytes survives above.
    for rel in ("src/screens/Downloads.tsx", "src/screens/MediaHub.tsx", "src/lib/downloads.ts", "src/lib/media.ts", "src/lib/share.ts"):
        remove_file(root, rel)

    # Final invariant scan over application and native sources.
    scan_roots = [root / "src", root / "android/app/src/main"]
    forbidden = ("Downloads.tsx", "MediaHub.tsx", "enqueueDownload", "analyzeLink",
                 "startDownload", "pauseDownload", "cancelDownload", "updateEngines", "openSniffer",
                 "DownloadManager", "yt-dlp", "gallery-dl", "N_m3u8DL", "aria2c",
                 "#/downloads", '"downloads"', '"Media Hub"', "Media Hub")
    hits = []
    for base in scan_roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.suffix not in {".ts", ".tsx", ".java", ".xml", ".kt"}:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for token in forbidden:
                if token in text:
                    hits.append(f"{p.relative_to(root)}: {token}")
    if hits:
        raise RuntimeError("Downloader-removal audit found stale references:\n" + "\n".join(hits[:80]))

    print("Downloader removal verified. Generic backup/export/QR/image-save flows were preserved.")


if __name__ == "__main__":
    main()
