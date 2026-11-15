# DAYFLOW Android Repair Audit

Audit target: `yousefrashadeltoor-svg/Yusif-3AMAK`  
Audited source: `comprehensive-repository-audit-and-roadmap.zip` (127 extracted files)  
Audit commit: `306dadce271178c253e7f0ccf4d4558281a8d328`

## Confirmed architecture gaps

1. The ZIP contains a React/Vite web application and `capacitor.config.ts`, but no Android project, Kotlin plugin, Android manifest, alarm receiver, overlay service, AppWidgetProvider, or native download engine.
2. `src/lib/nativeBridge.ts` expects a native Capacitor plugin named `DayflowBridge` through the legacy `window.Capacitor.Plugins` lookup. No matching native implementation exists in the archive, so the calls for alarms, device tones, widgets, overlay, link analysis, and downloads cannot work.
3. The APK workflow creates the Android platform during CI with `npx cap add android`; it does not add a DAYFLOW native plugin after generating the platform.
4. The companion robot is implemented as an in-app fixed-position React element. Its Document Picture-in-Picture fallback is browser-dependent; it is not an Android overlay service.
5. `WidgetHub.tsx` calls `pinWidget`, but without a native plugin and registered AppWidgetProvider, the current action only adds a design to the app's internal preview.
6. Alarm UI calls `scheduleAlarm` and `cancelAlarm`, but those calls currently have no Android implementation. The browser-only warning is also rendered unconditionally on the Alarms screen.
7. The SoundPicker asks the native bridge for tones but only stores the title, not a persistent Android URI; the selected device tone therefore cannot be passed to a native alarm scheduler.
8. `downloads.ts` tries native analysis first, but if the native plugin is missing it falls back to browser `fetch`/oEmbed/HEAD requests. Cross-origin restrictions explain why many sites fail. The current engine list names yt-dlp, NewPipe, gallery-dl, N_m3u8DL-RE and aria2c, but no Android binaries or native engine implementation are included in the ZIP.
9. Link preview relies on public oEmbed/fetch in `media.ts`; arbitrary websites commonly block cross-origin page reads. Android-side HTTP metadata extraction is needed for Open Graph title, image, description and author, while actual media formats must come from a real extractor and must not be fabricated.
10. Notification test and companion-hide flows use the browser Notification API. There is no Android notification permission flow, notification-channel implementation, or persistent reminder scheduler in the source archive.
11. Prayer times are calculated locally with a hard-coded city table and fixed UTC offsets. The table has Cairo but not Giza; there is no device-location selection or daylight-saving-aware time-zone database. The stated calculation method is Fajr 19.5°, Isha 17.5°, Asr standard/Shafi'i. Accuracy must be checked against the selected Egyptian authority/method and the user's actual city and date.
12. The companion animation calls React state setters on every animation frame, which can force the whole component to render at display refresh rate. This is a concrete performance hotspot to profile and reduce without changing its appearance.
13. The project contains web-only assumptions in clipboard access, notifications, file picking, and media probing. These need native equivalents where the feature requires system-level behavior.
14. The source's own status panel marks native alarm engine, device tones, native widgets, Filament companion and download engine as unverified. Those are not confirmed working features in the supplied archive.

## Required implementation order

### A. Native foundation
- Register a Capacitor 8 `DayflowBridge` plugin with `registerPlugin` on the TypeScript side and `@CapacitorPlugin` on Android.
- Add the Kotlin plugin and Android manifest declarations to the build pipeline, not just to a temporary generated folder.
- Keep the existing React/CSS/HTML interface and theme system. Native code should provide Android capabilities behind the bridge.

### B. Alarms and reminders
- Use `AlarmManager.setAlarmClock` for user-created alarm-clock events.
- Request/check `SCHEDULE_EXACT_ALARM` access and handle denial explicitly; restore alarms after boot, time changes and time-zone changes.
- Persist selected device sound URIs, vibration and repeat-day data.
- Deliver a high-priority alarm notification with an alarm sound channel and a launch action.
- Schedule task/reminder notifications through Android-native scheduling rather than page timers.

### C. Overlay robot
- Request `SYSTEM_ALERT_WINDOW` access only after explaining it to the user.
- Run a user-enabled foreground service using `TYPE_APPLICATION_OVERLAY`, with drag, tap-to-open, size and opacity settings.
- Stop the overlay when the user disables or hides the companion.
- The first native overlay implementation must be visually reviewed against the in-app robot; a simple Android bubble is not equivalent to the full animated companion.

### D. Home-screen widgets
- Add a real `AppWidgetProvider`, provider metadata/layout resources, data synchronization and a launcher pin request.
- Render real data and update after relevant app-state changes.
- Preserve the current widget catalog and preview, but do not claim all 137 web-rendered designs are native widgets until each native layout is implemented and tested.

### E. Downloads and previews
- Use Android-side HTTP for metadata so browser CORS does not block page previews.
- Show title, thumbnail, author, description, MIME type, filename, size and duration only when actually available.
- Use Android DownloadManager for direct files; use a real bundled/managed extractor for social/video sites. Do not show made-up formats or sizes.
- Surface unsupported sites, authentication requirements, DRM and unavailable extractor binaries honestly.
- Track native download state and progress in the same UI store.

### F. Notifications and permissions
- Add Android 13+ notification permission handling and dedicated channels.
- Replace browser Notification calls with the native notification method in APK mode.
- Keep browser compatibility messages only in the browser build.

### G. Prayer times
- Add Giza and accurate time-zone/DST handling; allow the selected city or a permission-based device location.
- Verify the calculation method and any local authority adjustments against an authoritative timetable for multiple dates and locations.
- Add tests around date boundaries, next-prayer rollover, polar/high-latitude handling and timezone transitions.

### H. Performance and regression checks
- Profile the companion animation and reduce React renders while preserving its current visuals and physics.
- Audit timers, intervals, event listeners, IndexedDB/localStorage operations, large Three.js scenes and image loading.
- Run TypeScript/Vite build, Android Gradle build, unit tests, static permission checks and an emulator/device smoke test.
- Verify alarm delivery with the app process closed, reboot recovery, overlay above a second app, widget pin/update, notification permission denial/grant, direct download completion, and link preview on both browser and Android.

## Important acceptance criteria

- No visual redesign or removal of existing features.
- Android system behavior must be implemented natively; the web layer remains the presentation/UI layer.
- No false “Android ready” labels or fake format/metadata results.
- CI build success is not proof of real-device behavior. Alarm, overlay, widget, notifications and download behavior require Android emulator/device validation.


---

## Execution update — 2026-11-15

This section supersedes any older assumptions above where the separate Android source archive was not yet inventoried, and records only results verified in the repair branch.

### Current architecture gate

- The canonical DAYFLOW source is still React/Vite/TypeScript with `capacitor.config.ts`; it is not a Kotlin/Jetpack Compose application.
- The previous successful Android build (run `43700009720`) compiled the Capacitor project and therefore produced a WebView-based application. It is explicitly disqualified under the new product requirement.
- `.github/workflows/build-apk.yml` now refuses to build or upload an APK unless the source contains a native `ComponentActivity` launcher using Compose `setContent`, Compose Gradle configuration, and no primary WebView/Capacitor shell.
- The current gate is expected to stop at source inspection. This is not an Android build failure after Gradle; Gradle is intentionally not run and no APK is created.

### Completed source cleanup

- Removed the downloader product surface from the DAYFLOW source: Downloads and Media Hub screens, route and navigation entry, downloader engine/planner code, downloader-only state, clipboard URL detection, URL/share-to-download handoff, downloader-only assistant routes, and three downloader-specific widget definitions.
- Removed downloader-specific bridge API members, URL-analysis helpers, direct-download methods and downloader wording from the retained Android native-source archive.
- Removed the downloader-only alarm sound picker choice while preserving user-owned legacy alarm sound references by migrating their source marker from `downloaded` to `files`; the alarm's saved URI is not discarded.
- Moved the shared byte-formatting helper to `src/lib/format.ts` so QR, image/file export, and other non-downloader tools keep their shared formatting behavior.
- Preserved unrelated task, calendar, habit, alarm, prayer, AI, QR/share, image editing/export, theme, widget, companion, and local media-library code.
- Added static invariant checks over the extracted source and native archive; those checks reject downloader-specific APIs, engine names, routes, labels and widget definitions.

### Catalog inventory and output

- The original DAYFLOW theme data contains 69 theme packs. The native catalog exporter writes the source values, bilingual labels, tokens, materials, shapes, font and motion metadata rather than inventing sample themes.
- The original widget catalog contains 140 definitions. Exactly three downloader-only definitions are excluded; 137 non-downloader definitions remain, across 12 categories, 10 styles and 6 widget font options.
- Catalog data export is not the same as native Compose rendering. The 69 theme previews and 137 launcher widget renderers have not yet been ported to Compose or individually tested.

### Verified CI results

For run `43703428485`:

- Native Compose source gate: **blocked as expected** because the archived project is still Capacitor/WebView.
- Theme/widget catalog extraction and validation: **passed**.
- Downloader removal and source invariant scan: **passed**.
- Native source archive sanitization and preservation checks: **passed**.
- Cleaned source Vite regression build: **passed**. This validates the remaining TypeScript/Vite source only; it is not an Android build.
- Cleaned source and catalog artifacts: **uploaded**.
- Native Compose Gradle build, APK validation, emulator install and physical-device tests: **not run**. No APK was built or published in this run.

Repair branch: `repair/native-compose-only-gate`  
Latest verified branch commit after persisting the cleaned source and native archive: `6ee83bb573d44ece71d7283b8c26a30b24d35575`.

### Remaining work

1. Build the complete native Kotlin/Jetpack Compose DAYFLOW UI from the existing DAYFLOW source of truth. Port every screen, dialog, navigation path, visual state, Arabic RTL/English LTR behavior, settings, persistence and business rule. Do not replace it with a simplified dashboard or a Capacitor wrapper.
2. Port all 69 theme definitions and theme preview/apply behavior into the Compose theme system. Preserve user theme selection, custom themes and all existing appearance options.
3. Implement real native launcher widget layouts and per-widget configuration for the 137 retained designs, or limit advertised native options to those actually implemented and tested. Do not claim the entire catalog is native merely because its data is exported.
4. Port alarm scheduling, saved device-tone URIs, permission recovery, reboot/time/time-zone restoration, continuous ringing, snooze and reminder actions into the native app. Existing archived Java components are reference implementations, not proof of runtime behavior.
5. Port the floating companion into a real system overlay/foreground service while preserving its existing appearance, controls and lifecycle behavior.
6. Implement notification permission/channels/actions and verify background delivery.
7. Validate Giza, Qalyub and Benha prayer calculations against the chosen Egyptian authority/method for multiple dates, using IANA time-zone data and appropriate local civil time. The previous city-offset patches are not an authoritative validation.
8. Run full native Gradle build, lint and unit tests; then emulator and physical-device tests for alarms, boot recovery, overlay, widgets, notifications, RTL/LTR, low-memory behavior and data persistence.
9. Add screenshot-based visual regression against the original DAYFLOW screens before switching the launcher to Compose.

### Scope correction

The earlier audit's download/extractor implementation plan is superseded by the user's explicit instruction to remove downloader tools entirely. No downloader, URL extractor, download queue, download engine, or media-sniffing replacement is in scope. Generic file export, backup, QR output, and local file references remain in scope where they are not part of the removed downloader product.
