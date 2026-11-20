import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job } from "../../lib/types";
import { QualityNote } from "./JobPage";

const job = (stats: unknown) => ({ id: "a", status: "done", mock: false, stats }) as unknown as Job;

describe("QualityNote", () => {
  it("tanpa data kualitas tidak menampilkan apa pun", () => {
    expect(renderToStaticMarkup(<QualityNote job={job({})} />)).toBe("");
  });
  it("menampilkan hitungan, temuan, dan catatan bukan-jaminan", () => {
    const html = renderToStaticMarkup(<QualityNote job={job({
      quality: { total: 5, by_severity: { blocker: 1, major: 2 }, auto_fixed: 3 },
      quality_findings: [{ rule_id: "CIT-001", severity: "blocker", subbab: "2.1 Konsep", message: "Sitasi (M dkk., 2026) tidak cocok." }],
    })} />);
    expect(html).toContain("Catatan mutu");
    expect(html).toContain("1 masalah serius");
    expect(html).toContain("2 masalah penting");
    expect(html).toContain("Sitasi (M dkk., 2026) tidak cocok.");
    expect(html).toContain("3 perbaikan kecil");
    expect(html).toContain("bukan jaminan mutu");
  });
  it("tanpa temuan berat menyatakan bersih, tetap dengan catatan", () => {
    const html = renderToStaticMarkup(<QualityNote job={job({ quality: { total: 2, by_severity: { minor: 2 } }, quality_findings: [] })} />);
    expect(html).toContain("tidak menemukan masalah berat");
    expect(html).toContain("bukan jaminan mutu");
  });
});
