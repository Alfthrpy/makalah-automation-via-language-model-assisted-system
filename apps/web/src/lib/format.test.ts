import { describe, expect, it } from "vitest";
import { clock, greeting, initials, resetCountdown, slug, whenLabel } from "./format";

describe("format", () => {
  const now = new Date("2026-11-19T10:00:00Z"); // 17.00 WIB
  it("whenLabel: hari ini, kemarin, tanggal", () => {
    expect(whenLabel("2026-11-19T02:41:00Z", now)).toBe("hari ini, 09.41");
    expect(whenLabel("2026-11-18T07:20:00Z", now)).toBe("kemarin, 14.20");
    expect(whenLabel("2026-11-17T13:05:00Z", now)).toMatch(/^17 Nov\.?, 20\.05$/);
    expect(whenLabel(null)).toBe("");
  });
  it("resetCountdown dari resets_at dan dari 00.00 WIB", () => {
    expect(resetCountdown("2026-11-20T00:00:00+07:00", now)).toBe("7 jam 0 menit");
    expect(resetCountdown(undefined, now)).toBe("7 jam 0 menit");
  });
  it("greeting menurut WIB", () => {
    expect(greeting(new Date("2026-11-19T02:00:00Z"))).toBe("Selamat pagi");
    expect(greeting(now)).toBe("Selamat sore");
    expect(greeting(new Date("2026-11-19T14:00:00Z"))).toBe("Selamat malam");
  });
  it("slug, initials, clock", () => {
    expect(slug("Analisis Sentimen: Naive Bayes!")).toBe("analisis-sentimen-naive-bayes");
    expect(initials("rina maharani putri")).toBe("RM");
    expect(clock(168)).toBe("2:48");
  });
});
