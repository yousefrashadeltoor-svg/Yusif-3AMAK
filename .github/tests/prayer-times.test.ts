import { describe, expect, it } from "vitest";
import { CITIES, prayerTimes } from "../src/lib/prayer";

const instant = new Date("2026-11-16T10:00:00.000Z"); // 12:00 in Cairo on the official comparison date.
const minutes = (value: string) => {
  const [hours, mins] = value.split(":").map(Number);
  return hours * 60 + mins;
};

describe("DAYFLOW prayer-time calculation", () => {
  it("matches the Egyptian General Survey Authority Cairo timetable within one minute", () => {
    const cairo = CITIES.find((city) => city.city === "Cairo");
    expect(cairo).toBeDefined();
    const result = prayerTimes(cairo!, instant);
    const official = { fajr: "04:51", sunrise: "06:21", dhuhr: "11:40", asr: "14:38", maghrib: "16:58", isha: "18:19" };
    for (const key of Object.keys(official) as Array<keyof typeof official>) {
      expect(Math.abs(minutes(result[key]) - minutes(official[key])), key).toBeLessThanOrEqual(1);
    }
    expect(result.next?.name).toBe("asr");
    expect(result.next?.inMin).toBe(minutes(result.asr) - 12 * 60);
  });

  it.each(["Giza", "Qalyub", "Benha"])("calculates a valid ordered local timetable for %s", (name) => {
    const city = CITIES.find((item) => item.city === name);
    expect(city).toBeDefined();
    const result = prayerTimes(city!, instant);
    const ordered = [result.fajr, result.sunrise, result.dhuhr, result.asr, result.maghrib, result.isha];
    expect(ordered.every((value) => /^\d{2}:\d{2}$/.test(value))).toBe(true);
    const values = ordered.map(minutes);
    for (let index = 1; index < values.length; index += 1) {
      expect(values[index]).toBeGreaterThan(values[index - 1]);
    }
    expect(result.next).not.toBeNull();
    expect(result.next!.inMin).toBeGreaterThan(0);
  });
});
