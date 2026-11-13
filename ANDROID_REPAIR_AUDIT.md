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
