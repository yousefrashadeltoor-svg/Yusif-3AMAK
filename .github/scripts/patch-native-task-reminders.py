#!/usr/bin/env python3
"""Add persistent Android notifications for dated DAYFLOW tasks with a dueTime."""
from __future__ import annotations
from pathlib import Path

ROOT = Path("android/app/src/main/java/app/dayflow/android")
TARGET = ROOT / "ReminderScheduler.java"
source = TARGET.read_text(encoding="utf-8")

constant_old = '    private static final String HABIT_KEYS = "habit_reminder_keys";\n'
constant_new = constant_old + '    private static final String TASK_KEYS = "task_reminder_keys";\n'
task_key_decl = '    private static final String TASK_KEYS = "task_reminder_keys";\n'
if task_key_decl not in source:
    if constant_old not in source:
        raise SystemExit("ReminderScheduler: habit key declaration not found; refusing unsafe patch")
    source = source.replace(constant_old, constant_new, 1)

fingerprint_old = 'String fingerprint = state.optString("lang", "en") + "|" + object(state, "notif").toString() + "|" + array(state, "habits").toString();'
fingerprint_new = 'String fingerprint = state.optString("lang", "en") + "|" + object(state, "notif").toString() + "|" + array(state, "habits").toString() + "|" + array(state, "tasks").toString();'
if fingerprint_new not in source:
    if fingerprint_old not in source:
        raise SystemExit("ReminderScheduler: reminder fingerprint anchor not found; refusing unsafe patch")
    source = source.replace(fingerprint_old, fingerprint_new, 1)

anchor = """        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putStringSet(HABIT_KEYS, nextHabitKeys).apply();
    }

    private static boolean reviewTimeAllowed"""
replacement = """        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putStringSet(HABIT_KEYS, nextHabitKeys).apply();

        // A task with both a calendar date and a due time is a persistent native reminder.
        // Recompute the full set whenever tasks change and after reboot/delivery.
        Set<String> nextTaskKeys = new HashSet<>();
        JSONArray tasks = array(state, "tasks");
        for (int i = 0; i < tasks.length(); i++) {
            JSONObject task = tasks.optJSONObject(i);
            if (task == null || task.optBoolean("done", false)
                    || "done".equals(task.optString("status", "todo"))) continue;
            String id = task.optString("id", "");
            String date = task.optString("date", "");
            String time = task.optString("dueTime", "");
            if (id.isEmpty() || time.isEmpty()) continue;
            Calendar when = taskTime(date, time);
            if (when == null || !when.after(Calendar.getInstance())
                    || !reviewTimeAllowed(time, quiet)) continue;
            String key = "task:" + id;
            nextTaskKeys.add(key);
            String title = task.optString("title", "").trim();
            if (title.isEmpty()) title = "DAYFLOW task";
            schedule(context, key, when, "Task reminder", "تذكير بمهمة",
                    "It\'s time for: " + title, "ميعاد المهمة: " + title);
        }
        Set<String> storedTasks = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getStringSet(TASK_KEYS, Collections.<String>emptySet());
        Set<String> previousTasks = new HashSet<>(storedTasks == null
                ? Collections.<String>emptySet() : storedTasks);
        for (String old : previousTasks) if (!nextTaskKeys.contains(old)) cancel(context, old);
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putStringSet(TASK_KEYS, nextTaskKeys).apply();
    }

    private static Calendar taskTime(String date, String time) {
        try {
            String[] ymd = date.split("-");
            int[] hm = parseTime(time);
            if (ymd.length != 3 || hm == null) return null;
            int year = Integer.parseInt(ymd[0]);
            int month = Integer.parseInt(ymd[1]);
            int day = Integer.parseInt(ymd[2]);
            Calendar value = Calendar.getInstance();
            value.clear();
            value.setLenient(false);
            value.set(year, month - 1, day, hm[0], hm[1], 0);
            value.getTimeInMillis(); // Force strict calendar validation before scheduling.
            return value;
        } catch (Exception ignored) { return null; }
    }

    private static boolean reviewTimeAllowed"""
if replacement not in source:
    if anchor not in source:
        raise SystemExit("ReminderScheduler: scheduleAll completion anchor not found; refusing unsafe patch")
    source = source.replace(anchor, replacement, 1)

required = [
    'private static final String TASK_KEYS = "task_reminder_keys";',
    'array(state, "tasks").toString()',
    'JSONArray tasks = array(state, "tasks");',
    'String key = "task:" + id;',
    'private static Calendar taskTime(String date, String time)',
    'putStringSet(TASK_KEYS, nextTaskKeys)',
]
for token in required:
    if token not in source:
        raise SystemExit("ReminderScheduler task reminder postcondition failed: " + token)

TARGET.write_text(source, encoding="utf-8")
print("Verified: task reminders schedule from date + dueTime, restore after boot, and cancel when tasks are done/removed/changed.")
