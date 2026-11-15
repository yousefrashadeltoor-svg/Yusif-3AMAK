# DAYFLOW — Native Android / UI Preservation Migration

Status: architecture blocker and implementation contract
Updated: 2026-11-15
Source repository: `yousefrashadeltoor-svg/Yusif-3AMAK`

## Non-negotiable product direction

- DAYFLOW remains the primary product. The current DAYFLOW screens, navigation, visual design, interaction behavior, business rules, and persisted data are the source of truth.
- This repository's existing theme and widget catalogs are reference material to reuse, not a replacement app and not permission to redesign DAYFLOW.
- The primary Android application UI must be a genuine native Kotlin + Jetpack Compose interface. A Capacitor `BridgeActivity`, Android `WebView`, local HTML shell, or website wrapper is not an acceptable app architecture.
- Downloader/media-extractor features are to be removed completely from DAYFLOW. Do not leave a hidden tab, route, screen, engine settings, download queue, native downloader API, URL sniffer, background download service, or placeholder controls. Preserve unrelated features and generic file export/share behavior only where it is not part of the downloader product.
- Never label an APK as ready merely because Gradle produced a valid archive. No WebView APK is an acceptable interim release.

## Verified source inventory

The source archive `comprehensive-repository-audit-and-roadmap.zip` contains 127 extracted source/build files. The actual application source is React 19 + Vite + TypeScript and includes `capacitor.config.ts`. Its Android launcher extends Capacitor `BridgeActivity`. Therefore the successful Android build recorded in Actions run `43700009720` is a successful Capacitor/WebView build, not a native Compose application.

The DAYFLOW source already contains reusable design data:

- 69 theme packs in `src/lib/themes.ts`, including palette, material, shape, typography, motion, texture, and ornament affinity.
- 140 widget definitions in `src/lib/widgets.ts`, grouped into 12 categories and using 33 widget archetypes.
- 10 widget visual styles, 6 widget font choices, and 6 declared widget sizes.
- Existing theme preview/apply logic, widget catalog, placement model, widget data model, RTL/LTR handling, and localized Arabic/English labels.

These catalogs must be preserved and ported as data/models, not replaced with a small hand-picked subset. Each theme preview must render the actual theme treatment; each native widget must render real DAYFLOW state and be tested at its declared size. A catalog entry must not be advertised as a working launcher widget until its native layout/provider exists and passes launcher testing.

## Required native architecture

1. Create a complete Android Gradle application using Kotlin and Jetpack Compose. The launcher must extend `ComponentActivity` and render the app with `setContent { ... }`.
2. Port every existing DAYFLOW screen and shared component without simplifying or removing product behavior. Keep the current visual source as the comparison reference.
3. Port theme tokens and all 69 theme definitions. Preserve custom themes, favorites, automatic time-based themes, surface-specific themes, and current persistence semantics.
4. Port all 140 widget definitions, categories, archetypes, forms, and styles. Implement real AppWidgetProvider instances, responsive RemoteViews/Glance layouts, per-widget configuration, launcher pinning, real state updates, and restoration.
5. Implement alarms, reminders, notifications, device sound URIs, floating companion service, permissions, and boot/time-change restoration as native Android services and receivers.
6. Preserve the current prayer-time calculation intent, validate Egyptian method/settings and civil-time-zone behavior, and test Giza, Qalyub, and Benha against a trusted Egyptian timetable.
7. Preserve app identity, storage semantics, user settings, and a documented non-destructive migration path. Never silently wipe existing user data.
8. Add screenshot/behavior regression tests for Arabic RTL and English LTR, light/dark themes, custom themes, every screen, widget previews, and supported display sizes.

## Complete downloader removal scope

Remove downloader-specific functionality from the product source and Android integration, including:

- Downloads tab, route, screen, navigation icon, related dialogs, format selection, queue/history/progress UI, and downloader-only settings.
- Download engine registry, engine planner/fallback chain, URL sniffer, media extractor interfaces, download-specific state/store fields, and downloader-only metadata parsing.
- Native bridge methods and Android implementations for enqueue/start/pause/cancel downloads, engine updates, and sniffer launch.
- Download-specific foreground services, receivers, notifications/channels, permissions, manifest declarations, dependencies, and build steps where no other DAYFLOW feature uses them.
- Download-only share-intent routing and URL-to-download handoff.

Do not remove unrelated calendar, alarm, task, habit, AI, QR/share, theme, widget, media-display, image-edit/export, or other existing DAYFLOW features. Before deleting a shared helper, inspect all call sites and retain or split any non-downloader behavior still used elsewhere. After removal, run repository-wide reference scans so no dead imports, route names, settings, native methods, labels, or build artifacts remain.

## Build and release gate

The repository workflow now rejects source archives that do not contain a complete native Compose Android project. It must reject Capacitor/WebView and static website wrappers rather than creating a misleading APK. The gate is intentionally expected to fail against the current React/Capacitor archive until the real Compose migration is supplied.

Required checks before a native APK may be uploaded:

- Native source gate passes; no primary WebView/Capacitor shell.
- Kotlin/Compose compilation, Android lint, unit tests, and source-level regression tests pass.
- APK integrity, manifest, DEX, and absence of website-shell assets are verified.
- Install and smoke-test on an Android emulator, then validate critical system behavior on a physical device.
- Report build success separately from emulator/device verification. Never claim physical-device testing unless it happened.

## Immediate blocker

The repository currently stores the DAYFLOW app only as a React/Vite + Capacitor source archive. The successful run `43700009720` compiled that Capacitor project and uploaded an APK; it did not produce a native Compose UI. The next real implementation task is the full native Compose port while using the existing DAYFLOW theme/widget catalogs as the source data. Until that is done, the build workflow must not publish a WebView APK.
