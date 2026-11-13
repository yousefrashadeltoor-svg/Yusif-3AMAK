# DAYFLOW Android Repair Backlog

Updated: 2026-11-13
Repository: `yousefrashadeltoor-svg/Yusif-3AMAK`

## Verified current state

- The application source is stored in `comprehensive-repository-audit-and-roadmap.zip`; it is not checked into the repository as unpacked source files.
- `.github/workflows/build-apk.yml` extracts that archive and builds the Android app with Capacitor 8.
- The Android build therefore still launches the web UI through Capacitor's WebView. A native Java plugin provides selected system features, but this is not a Jetpack Compose UI migration.
- `android-native/native-source.zip.b64` contains native Android source that the workflow extracts during CI.
- `.github/scripts/patch-native-alarms.py` patches exact-alarm permission handling, alarm restoration, selected device sound URI, continuous ringing and vibration.
- The latest build at commit `a97a5340707b89517cec522a96415bd39aed4f18` completed successfully. This confirms compilation and artifact upload only; it does not confirm real-device runtime behavior.
- The latest build artifact is associated with run `43423703805`.

## Complete repair checklist — ordered

### P0 — Native app architecture and UI parity

- [ ] Replace the Capacitor/WebView application shell with a genuine Kotlin + Jetpack Compose Android application.
- [ ] Port every existing screen, component, dialog, sheet, menu, animation, theme, typography, spacing, icon, and RTL/LTR behavior to Compose.
- [ ] Preserve the original UI as the pixel-level reference; do not simplify, redesign, remove, or rename existing screens and features.
- [ ] Preserve all application logic and data semantics while replacing browser-only implementations with Android services and repositories.
- [ ] Keep WebView only for content that inherently requires web rendering; it must not host the primary app UI.
- [ ] Add screenshot-based visual regression coverage for each screen, theme, language, and supported screen size before switching the launcher activity.
- [ ] Preserve the existing app identity, application ID, persisted user data, and upgrade path. Do not silently wipe or migrate user data.

### P1 — Alarms, reminders, sounds, and time display

- [ ] Verify the exact-alarm permission flow on Android 12+ and the post-grant return path.
- [ ] Verify alarms while the app is closed, process killed, device locked, and after reboot.
- [ ] Verify one-time alarms are removed after firing and repeating alarms calculate the next occurrence correctly.
- [ ] Verify time-zone changes, manual clock changes, daylight-saving transitions, and reboot restoration.
- [ ] Verify the selected ringtone URI remains readable after process death and is passed to the alarm receiver.
- [ ] Verify continuous alarm audio, vibration, dismissal, snooze, and notification cancellation on physical Android devices.
- [ ] Implement scheduled reminders with Android-native scheduling; an immediate notification test is not proof of persistent reminders.
- [ ] Use a strict 12-hour clock throughout the app, including alarm editor, cards, notifications, widgets, prayer times, and spoken reminders. Respect the Arabic locale digits where the design already does so.
- [ ] Hide browser-only warnings and capability notices in the Android build; show them only in browser mode.

### P2 — Floating companion robot

- [ ] Verify `SYSTEM_ALERT_WINDOW` access is requested through Android Settings and rechecked when the user returns.
- [ ] Verify a foreground service owns the overlay and that the robot remains visible above other apps and the launcher.
- [ ] Verify drag, tap-to-open, close/hide, size, opacity, orientation changes, and service restart behavior.
- [ ] Add a clear persistent notification while the overlay service is active, with a stop action.
- [ ] Respect Android background-start and foreground-service restrictions; do not claim an overlay is active when permission or service startup fails.
- [ ] Keep the robot's existing appearance and animation; profile frame updates and avoid triggering a full UI recomposition every animation frame.

### P3 — Real Android home-screen widgets

- [ ] Implement real Android AppWidget providers and supported widget layouts, not only in-app previews.
- [ ] Support each advertised widget size with the appropriate native layout and responsive content.
- [ ] On launcher pin/add flow, save the requested size/design, open DAYFLOW directly to the existing widget-selection screen, and let the user choose the design for that widget instance.
- [ ] Return the selected design to the matching widget instance and render it on the home screen.
- [ ] Persist widget configuration per widget ID and restore it after reboot or app update.
- [ ] Update widget content from real app state and provide explicit refresh/update handling.
- [ ] Do not advertise a design or size as available until its native layout exists and has passed launcher testing.

### P4 — Link preview, media metadata, and downloads

- [ ] Remove browser CORS-dependent page scraping from Android link analysis.
- [ ] Fetch page metadata natively and display only verified title, thumbnail/cover, author, description, duration, filename, MIME type, and file size.
- [ ] Support common Open Graph and site metadata, with robust timeouts, redirects, charset handling, and clear unsupported-page errors.
- [ ] Use Android DownloadManager for actual direct-file URLs and show real progress, pause/resume/cancel support where available, and final destination.
- [ ] Integrate a maintained Android-compatible media extractor for supported video/social sites; do not invent formats, resolutions, or sizes.
- [ ] Detect and explain unsupported sites, login requirements, DRM, expired URLs, and unavailable extractors.
- [ ] Ensure choosing a format starts the real native download rather than a browser request or simulated progress.
- [ ] Persist download state across app restarts and handle Android storage/media permissions correctly.

### P5 — Notifications and Android permissions

- [ ] Implement notification permission requests on Android 13+ with a clear denied-permission recovery path.
- [ ] Create distinct channels for alarms, reminders, companion status, and download progress.
- [ ] Implement actionable notifications with the exact behavior designed in the app (open, complete, snooze, dismiss).
- [ ] Ensure notification actions work when the app process is not running.
- [ ] Keep browser Notification API behavior isolated to browser builds.

### P6 — Prayer times and seasonal decoration

- [ ] Replace hard-coded city offsets with timezone-database-based local date/time handling.
- [ ] Support device location only after permission and provide a manual city fallback.
- [ ] Validate the selected calculation method, Fajr/Isha angles, Asr school, and local adjustments against an authoritative Egyptian timetable.
- [ ] Test Giza, Qalyubia, Cairo, Alexandria, date boundaries, daylight-saving changes, and next-prayer rollover.
- [ ] Add unit tests for astronomical calculations and ensure prayer times are not presented as authoritative until verified.
- [ ] Replace low-quality synthetic seasonal decorations with real, properly licensed, optimized assets for additional seasons.
- [ ] Preserve the existing leaf decorations and visual composition; add new realistic seasonal sets without changing the app's layout or theme.

### P7 — Performance and stability

- [ ] Profile cold start, navigation, animation, image loading, IndexedDB/state persistence, and large visual scenes.
- [ ] Remove unnecessary render loops and expensive per-frame React state updates before the UI port; implement equivalent efficient Compose animation primitives in the native UI.
- [ ] Avoid blocking the main thread for media metadata, downloads, database operations, prayer calculations, and image decoding.
- [ ] Add lifecycle-safe cancellation for jobs, listeners, timers, and services.
- [ ] Add crash logging and actionable error states without exposing developer diagnostics in the user-facing UI.
- [ ] Test low-memory devices, background/foreground transitions, rotation, process recreation, and weak network conditions.

## Required verification gates

1. Source and feature inventory completed against the extracted project archive.
2. Unit tests for alarm scheduling, date/time, prayer calculations, link metadata parsing, and widget configuration pass.
3. Android lint and permission checks pass.
4. Debug and release Gradle builds pass.
5. Emulator tests cover alarm, notification, overlay, widget pinning, link preview, and direct downloads.
6. Physical-device tests confirm alarms, overlay, widgets, and notifications under real Android restrictions.
7. Screenshot comparisons demonstrate the Compose UI matches the existing design before the WebView shell is removed.

## Non-negotiable constraints

- Do not change the app's visual design, navigation, feature set, or user-facing wording except for the requested Android/browser capability-message distinction and the requested 12-hour time format.
- Do not substitute mock data, simulated download formats, fake alarms, or preview-only widgets for real Android functionality.
- Do not mark a feature complete based solely on a successful APK build.
- Do not remove the existing app until the replacement has passed visual and functional regression tests.
