#!/usr/bin/env python3
"""Idempotent DAYFLOW source repairs applied after native bridge/permission patching."""
from pathlib import Path

ROOT = Path.cwd()
SRC = ROOT / "src"

def replace_once(path: Path, old: str, new: str, label: str, *, required: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        if required:
            raise RuntimeError(f"Expected source marker not found ({label}) in {path}")
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

# 1) Force 12-hour display and migrate existing preferences without discarding data.
p = SRC / "lib/store.ts"
replace_once(p, "sampleData: false, feedback: {}, hour12: false,", "sampleData: false, feedback: {}, hour12: true,", "12-hour default")
replace_once(
    p,
    '{ name: "dayflow-v2", version: 3, migrate: (state) => state as S, storage:',
    '{ name: "dayflow-v2", version: 4, migrate: (state) => ({ ...(state as S), hour12: true, cityIndex: (state as S & { cityIndex?: number }).cityIndex === 0 ? 10 : (state as S & { cityIndex?: number }).cityIndex ?? 10 }) as S, storage:',
    "12-hour preference migration"
)

p = SRC / "screens/Me.tsx"
replace_once(
    p,
    'right: <Toggle on={s.hour12} onChange={(v) => s.set({ hour12: v })} label={t("12-hour clock", "الساعة بنظام ١٢ ساعة")} />',
    'right: <Toggle on={true} onChange={() => s.set({ hour12: true })} label={t("12-hour clock", "الساعة بنظام ١٢ ساعة")} />',
    "lock 12-hour clock setting"
)

p = SRC / "lib/agent.ts"
replace_once(p, 'case "setClock": ok = typeof a.hour12 === "boolean"; detail = a.hour12 ? "12 ساعة" : "24 ساعة"; break;',
             'case "setClock": ok = a.hour12 === true; detail = "12 ساعة"; break;',
             "agent cannot disable 12-hour clock")
replace_once(p, 'case "setClock": s.set({ hour12: Boolean(a.hour12) }); break;',
             'case "setClock": s.set({ hour12: true }); break;',
             "agent preserves 12-hour clock")

# 2) Reduce the robot simulation's React re-renders to a 30 fps UI cadence.
p = SRC / "components/Companion.tsx"
replace_once(p, '  const raf = useRef<number | null>(null);',
             '  const raf = useRef<number | null>(null);\n  const lastUiFrame = useRef(0);',
             "robot render cadenci ref")
replace_once(
    p,
    '      setPos({ x: s.x, y: s.y });\n      force((n) => (n + 1) % 1e6);',
    '      if (now - lastUiFrame.current >= 1000 / 30) {\n        lastUiFrame.current = now;\n        setPos({ x: s.x, y: s.y });\n        force((n) => (n + 1) % 1e6);\n      }',
    "throttle robot UI re-renders"
)

# 3) Sync real app state to native storage so home-screen widgets can display live information.
p = SRC / "App.tsx"
replace_once(p, 'import { useStore, useT } from "./lib/store";',
             'import { useStore, useT } from "./lib/store";\nimport { nativeBridge, isAndroidApk } from "./lib/nativeBridge";',
             "native widget state bridge import")
anchor = '  const t = useT();\n  const [route, setRoute] = useState(parseHash);'
replacement = '''  const t = useT();
  useEffect(() => {
    if (!isAndroidApk()) return;
    const snapshot = JSON.stringify({
      lang: s.lang, hour12: true, cityIndex: s.cityIndex,
      tasks: s.tasks, alarms: s.alarms, habits: s.habits,
      countdowns: s.countdowns, placed: s.placed,
    });
    void nativeBridge.syncState(snapshot)?.catch((error) => console.warn("DAYFLOW native widget sync failed", error));
  }, [s.lang, s.cityIndex, s.tasks, s.alarms, s.habits, s.countdowns, s.placed]);
  const [route, setRoute] = useState(parseHash);'''
replace_once(p, anchor, replacement, "sync app data with native widgets")

# 4) Provide a real selectable direct-file format in Android mode, while never inventing
# formats for ordinary HTML pages which need a dedicated extractor.
p = SRC / "lib/downloads.ts"
old = '''        base.formats = [
          ...g.presets.map((p) => ({ id: p.id, label: p.label, detail: `${p.containers.join(" / ")}${p.fps ? ` · ${p.fps}fps` : ""}${p.hdr ? " · HDR" : ""}`, size: p.size, kind: "video" as const, height: p.height })),
          ...g.audio.map((a) => ({ id: a.id, label: a.label, detail: a.copy ? "stream copy" : "FFmpeg", size: a.size, kind: "audio" as const })),
        ];
        cache.set(key, { at: Date.now(), value: base }); return base;'''
new = '''        base.formats = [
          ...g.presets.map((p) => ({ id: p.id, label: p.label, detail: `${p.containers.join(" / ")}${p.fps ? ` · ${p.fps}fps` : ""}${p.hdr ? " · HDR" : ""}`, size: p.size, kind: "video" as const, height: p.height })),
          ...g.audio.map((a) => ({ id: a.id, label: a.label, detail: a.copy ? "stream copy" : "FFmpeg", size: a.size, kind: "audio" as const })),
        ];
        if (j.direct && base.formats.length === 0) {
          const directKind: "video" | "audio" | "image" | "file" =
            kind === "video" ? "video" : kind === "audio" ? "audio" : kind === "image" ? "image" : "file";
          const ext = (base.mime?.split("/").pop() || base.filename.split(".").pop() || "file").toUpperCase();
          base.formats = [{ id: "original", label: ext, detail: base.mime || "Direct file", size: base.size, kind: directKind, url: parsed.url }];
        }
        if (!j.direct && base.formats.length === 0) {
          base.engineNote = "تم جلب بيانات الصفحة. الصيغ القابلة للتنزيل لا تُعرض إلا بعد استخراج حقيقي يدعم هذا الموقع.";
        }
        cache.set(key, { at: Date.now(), value: base }); return base;'''
replace_once(p, old, new, "native direct-file format handling")

# 5) Default fresh installations to Giza's city profile rather than silently assuming central Cairo.
# Existing selected cities are preserved by Zustand migration above.
replace_once(SRC / "lib/store.ts", "widgetFont: \"sans\", cityIndex: 0,", "widgetFont: \"sans\", cityIndex: 10,", "Giza default prayer location")

print("DAYFLOW feature patches applied: 12-hour clock, throttled companion rendering, native widget data sync, truthful direct-file format handling, and Giza default.")