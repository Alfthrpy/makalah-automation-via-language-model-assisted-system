import { describe, expect, it } from "vitest";
import { elapsedLabel, jobPct, stepSeconds, summaryPct, FALLBACK_STEPS } from "./jobUtils";
import type { Job, JobSummary } from "../../lib/types";

const base = { id: "a", title: "t", created_at: "", mock: false, has_file: false } as const;

describe("jobUtils", () => {
  it("summaryPct menghitung tahap selesai + setengah tahap berjalan", () => {
    const j = { ...base, status: "running", progress: { done: 3, total: 7 }, current_step: "tulis" } as JobSummary;
    expect(summaryPct(j)).toBe(50);
    expect(summaryPct({ ...j, progress: null })).toBe(0);
  });
  it("jobPct dari steps detail", () => {
    const steps = Object.fromEntries(FALLBACK_STEPS.map((s) => [s.key, { status: "pending", detail: "" }]));
    steps.input = { status: "done", detail: "" };
    steps.outline = { status: "running", detail: "" };
    const job = { ...base, status: "running", steps, log: [] } as unknown as Job;
    expect(jobPct(job, FALLBACK_STEPS)).toBe(Math.round((1.5 / FALLBACK_STEPS.length) * 100));
  });
  it("stepSeconds dan elapsedLabel", () => {
    expect(stepSeconds({ status: "done", detail: "", started_at: "2026-01-01T00:00:00Z", finished_at: "2026-01-01T00:02:48Z" })).toBe(168);
    expect(stepSeconds({ status: "done", detail: "" })).toBeNull();
    expect(elapsedLabel("2026-01-01T00:00:00Z", "2026-01-01T00:19:29Z")).toBe("19 mnt 29 dtk");
  });
});
