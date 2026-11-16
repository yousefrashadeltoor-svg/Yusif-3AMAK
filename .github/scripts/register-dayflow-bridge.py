#!/usr/bin/env python3
"""Register DAYFLOW's local Capacitor plugin after every cap sync."""
from __future__ import annotations

import os
from pathlib import Path

project_root = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
activity = project_root / "android/app/src/main/java/app/dayflow/android/MainActivity.java"
if not activity.is_file():
    raise SystemExit(f"Native bridge registration blocked: {activity} is missing.")

source = activity.read_text(encoding="utf-8")
package_marker = "package app.dayflow.android;"
class_marker = "public class MainActivity extends BridgeActivity {"
plugin_call = "registerPlugin(DayflowBridgePlugin.class);"

if package_marker not in source or class_marker not in source:
    raise SystemExit("Unexpected MainActivity structure; refusing an unsafe rewrite.")

if "import android.os.Bundle;" not in source:
    source = source.replace(package_marker, package_marker + "\n\nimport android.os.Bundle;", 1)

if source.count(plugin_call) > 1:
    raise SystemExit("Duplicate DAYFLOW native plugin registration was detected.")

if plugin_call not in source:
    class_start = source.index(class_marker) + len(class_marker)
    method_signature = "onCreate(Bundle savedInstanceState)"
    if method_signature in source:
        method_start = source.index(method_signature)
        super_call = "super.onCreate(savedInstanceState);"
        super_pos = source.find(super_call, method_start)
        if super_pos < 0:
            raise SystemExit("MainActivity.onCreate has no expected super call.")
        source = source[:super_pos] + plugin_call + "\n        " + source[super_pos:]
    else:
        method = (
            "\n    @Override\n"
            "    public void onCreate(Bundle savedInstanceState) {\n"
            f"        {plugin_call}\n"
            "        super.onCreate(savedInstanceState);\n"
            "    }\n"
        )
        source = source[:class_start] + method + source[class_start:]

if source.count(plugin_call) != 1 or "onCreate(Bundle savedInstanceState)" not in source:
    raise SystemExit("DAYFLOW native bridge registration postcondition failed.")

activity.write_text(source, encoding="utf-8")
print("Verified DAYFLOW DayflowBridge registration in the final post-sync MainActivity.")
