import { beforeEach, describe, expect, it } from "vitest";
import { DRAFT_KEY, REFILL_KEY, defaultForm, loadDraft, saveDraft, serializeDraft, takeRefill, sampleForm } from "./formState";

beforeEach(() => localStorage.clear());

describe("draf formulir", () => {
  it("TIDAK pernah menyimpan API key", () => {
    const f = { ...defaultForm(), judul: "Judul Uji", api_key: "sk-rahasia-12345678", save_key: true };
    const raw = serializeDraft(f);
    expect(raw).not.toContain("sk-rahasia");
    expect(raw).not.toContain("api_key");
    saveDraft(f);
    expect(localStorage.getItem(DRAFT_KEY)).not.toContain("sk-rahasia");
  });
  it("memulihkan isian tetapi key kosong", () => {
    saveDraft({ ...sampleForm(defaultForm()), api_key: "sk-rahasia-12345678" });
    const back = loadDraft(defaultForm());
    expect(back?.judul).toContain("Gamifikasi");
    expect(back?.penyusun).toHaveLength(3);
    expect(back?.api_key).toBe("");
    expect(back?.save_key).toBe(false);
  });
  it("draf rusak diabaikan", () => {
    localStorage.setItem(DRAFT_KEY, "{bukan json");
    expect(loadDraft(defaultForm())).toBeNull();
  });
});

describe("isi ulang dari job lama", () => {
  it("dipakai sekali lalu dibuang", () => {
    localStorage.setItem(REFILL_KEY, JSON.stringify({ request: { judul: "A B C", mata_kuliah: "MK", penyusun: [{ nama: "X", nim: "1" }], tahun: "2025" }, mock: true }));
    const f = takeRefill(defaultForm());
    expect(f).toMatchObject({ judul: "A B C", mata_kuliah: "MK", mock: true, tahun: "2025" });
    expect(f?.penyusun[0]).toMatchObject({ nama: "X", nim: "1" });
    expect(localStorage.getItem(REFILL_KEY)).toBeNull();
    expect(takeRefill(defaultForm())).toBeNull();
  });
});
