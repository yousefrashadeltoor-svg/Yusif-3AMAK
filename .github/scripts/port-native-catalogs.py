#!/usr/bin/env python3
"""Extract DAYFLOW's real theme/widget catalog data for the native migration."""
from __future__ import annotations
import argparse, ast, json, re
from pathlib import Path

REMOVED_WIDGETS = {"Active downloads", "Paste-link tile", "Download history"}

def slug(value: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))

def quoted_rows(block: str):
    rows = []
    for line in block.splitlines():
        candidate = line.strip().rstrip(",")
        if candidate.startswith("["):
            row = ast.literal_eval(candidate)
            if isinstance(row, list):
                rows.append(row)
    return rows

def extract_themes(lib: Path) -> dict:
    source = (lib / "themes.ts").read_text(encoding="utf-8")
    block = source.split("const R: Row[] = [", 1)[1].split("\n];", 1)[0]
    themes = []
    for row in quoted_rows(block):
        if len(row) != 15:
            raise ValueError(f"Unexpected theme row shape: {row!r}")
        en, ar, category, mode, bg, surface, text, accent, accent2, material, shape, font, motion, texture, ornament = row
        themes.append({
            "id": slug(en), "en": en, "ar": ar, "category": category,
            "mode": "light" if mode == "l" else "dark",
            "background": bg, "surface": surface, "text": text,
            "accent": accent, "accent2": accent2, "material": material,
            "shape": shape, "font": font, "motion": motion,
            "texture": texture, "ornament": ornament, "version": 1,
        })
    category_block = source.split("export const CATEGORIES:", 1)[1].split("\n];", 1)[0]
    categories = [{"id": i, "en": e, "ar": a} for i, e, a in re.findall(
        r'id: "([^"]+)", en: "([^"]+)", ar: "([^"]+)"', category_block)]
    if len(themes) != 69:
        raise ValueError(f"Theme source count changed: expected 69, found {len(themes)}")
    if len({x["id"] for x in themes}) != len(themes):
        raise ValueError("Theme IDs are not unique")
    return {"schemaVersion": 1, "source": "src/lib/themes.ts", "count": len(themes),
            "categories": categories, "themes": themes}

def extract_widgets(lib: Path) -> dict:
    source = (lib / "widgets.ts").read_text(encoding="utf-8")
    block = source.split("const C: Record<WCat, Row[]> = {", 1)[1].split("\n};", 1)[0]
    raw, category, indices = [], None, {}
    pattern = re.compile(r'\["((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)",\s*"([^"]+)",\s*([01])\]')
    for line in block.splitlines():
        match = re.match(r"\s*([a-zA-Z]+):\s*\[", line)
        if match:
            category = match.group(1)
        if category:
            raw.extend((category, en, ar, archetype, int(interactive))
                       for en, ar, archetype, interactive in pattern.findall(line))
    if len(raw) not in (137, 140):
        raise ValueError(f"Widget source count changed: expected 140 before downloader removal or 137 after it, found {len(raw)}")
    widgets = []
    for category, en, ar, archetype, interactive in raw:
        if en in REMOVED_WIDGETS:
            continue
        variant = indices.get(category, 0)
        indices[category] = variant + 1
        forms = (["2x2", "4x2", "4x4"] if archetype in {"matrix", "kanban", "month"}
                 else ["2x1", "2x2", "4x2", "4x4"] if archetype == "note"
                 else ["1x1", "2x1", "2x2", "4x1", "4x2", "4x4"])
        widgets.append({
            "id": f"{category}-{slug(en)}", "en": en, "ar": ar,
            "category": category, "archetype": archetype, "variant": variant,
            "interactive": bool(interactive), "forms": forms,
        })
    if len(widgets) != 137:
        raise ValueError(f"Native widget count changed: expected 137, found {len(widgets)}")
    if any(x["archetype"] == "download" or x["en"] in REMOVED_WIDGETS for x in widgets):
        raise ValueError("Downloader-only widget leaked into native widget catalog")
    if len({x["id"] for x in widgets}) != len(widgets):
        raise ValueError("Widget IDs are not unique")
    category_block = source.split("export const WCATS:", 1)[1].split("\n];", 1)[0]
    categories = [{"id": i, "en": e, "ar": a} for i, e, a in re.findall(
        r'id: "([^"]+)", en: "([^"]+)", ar: "([^"]+)"', category_block)]
    styles_block = source.split("export const WSTYLES:", 1)[1].split("\n];", 1)[0]
    styles = [{"id": i, "en": e, "ar": a} for i, e, a in re.findall(
        r'id: "([^"]+)", en: "([^"]+)", ar: "([^"]+)"', styles_block)]
    fonts_block = source.split("export const WIDGET_FONTS:", 1)[1].split("\n};", 1)[0]
    fonts = {i: {"en": e, "ar": a, "stack": stack} for i, e, a, stack in re.findall(
        r'([a-zA-Z]+): \{ en: "([^"]+)", ar: "([^"]+)", stack: \x60([^\x60]*)\x60 \}', fonts_block)}
    return {
        "schemaVersion": 1, "source": "src/lib/widgets.ts",
        "sourceCount": len(raw), "count": len(widgets),
        "removedDownloaderDefinitions": sorted(REMOVED_WIDGETS),
        "forms": ["1x1", "2x1", "2x2", "4x1", "4x2", "4x4"],
        "categories": categories, "styles": styles, "fonts": fonts, "widgets": widgets,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-lib", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    themes, widgets = extract_themes(args.source_lib), extract_widgets(args.source_lib)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in (("themes.json", themes), ("widgets.json", widgets)):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "validated", "themeCount": themes["count"],
        "themeCategories": len(themes["categories"]), "sourceWidgetCount": widgets["sourceCount"],
        "nativeWidgetCount": widgets["count"], "removedDownloaderWidgets": widgets["removedDownloaderDefinitions"],
        "widgetCategories": len(widgets["categories"]), "widgetStyles": len(widgets["styles"]),
        "widgetFonts": len(widgets["fonts"]),
        "note": "Catalog data is ported; native screens/widgets still require rendering implementation and device testing.",
    }
    (args.output / "catalog-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
