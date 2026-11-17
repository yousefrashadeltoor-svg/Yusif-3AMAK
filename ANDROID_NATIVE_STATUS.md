# DAYFLOW native Android migration status

The `.github/native-dayflow-source.part-*` files reconstruct a compressed standalone Android Gradle project. Its launcher is a Kotlin `ComponentActivity` using Jetpack Compose. The native project contains no Capacitor or WebView launcher classes. The old Capacitor project remains in the repository for source/reference audit only, and its workflow is manual-only with an explicitly legacy artifact name.

## Implemented in this native migration pass

- Jetpack Compose screens for Today, Calendar, Alarms, Tools, Assistant, Downloads and Settings.
- Local SharedPreferences persistence for tasks, alarms, habits, hydration, language, theme and 12/24-hour clock choice.
- Android AlarmManager alarms, repeat days, exact-alarm access handling, boot/time-change restoration, snooze, ringtone selection via Android document picker with persisted URI access, vibration and a native ringing activity.
- Scheduled task reminders and a one-tap notification action to complete a task.
- Two real Android home-screen widgets: daily task overview and hydration/next-alarm overview. Both update when tasks, hydration, or alarms change and can be requested separately from Settings.
- Foreground companion overlay with a persistent stop notification, touch drag and RTL/LTR-aware movement. The current companion is native 2D artwork, not a 3D model renderer.
- Android DownloadManager for direct file URLs only. Social/video page extraction is not included and no formats/sizes are fabricated.
- Arabic/English and RTL/LTR switching, 12/24-hour display and input, and dashboard-style visual previews for the included themes.
- Instrumentation test for primary Compose navigation, alarm editor, settings, widget choices and theme preview.

## Not complete — do not describe this build as full feature parity

- Full one-to-one migration of every screen, dialog, component, data model, animation, decoration and business rule in the original React source archive.
- Original complete theme collection, all original widget designs/sizes and per-widget visual editor/configuration.
- Full 3D companion pipeline: importing arbitrary 3D formats, real-time model rendering in the floating overlay, model animation and model settings.
- Connected AI provider setup, secure key storage, conversations/history and remote assistant actions. The current assistant performs only a few explicit offline commands.
- Full download engine/media extractor, playlist/site support, subtitles, format enumeration, rich URL metadata and download history controls. Only direct file URLs are delegated to Android DownloadManager.
- Prayer-time calculations, location/time-zone selection and validation against authoritative local timetables.
- QR tools, full media utilities, theme/widget import/export, and complete screenshot-based visual regression against every original screen and device size.
- Migration of existing browser IndexedDB/localStorage data into native storage. Existing browser data is not automatically copied to the new SharedPreferences store.
- Physical-device validation on the target Infinix phone for exact alarms, notifications, overlay policy, launcher widgets, reboot and battery restrictions.

## Verification gates

The native GitHub Actions workflow must pass Gradle compilation, lint, unit tests, APK signature/package/DEX inspection, instrumentation navigation tests, installation and cold-launch on an Android 35 emulator before its APK artifact can be called verified. Emulator success still does not replace physical-device testing.
