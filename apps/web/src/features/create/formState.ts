import { store } from "../../lib/storage";
import type { PaperRequest, ProviderInfo } from "../../lib/types";
import { MAX_PENYUSUN, emptyPenyusun, type PaperForm } from "../../lib/validation";

export const DRAFT_KEY = "malas.draft.v1";
export const REFILL_KEY = "malas.refill.v1";

let seq = 0;
export const newRid = () => `r${Date.now().toString(36)}${(seq++).toString(36)}`;

export const SAMPLE: Omit<PaperForm, "template" | "mock" | "provider" | "keySource" | "api_key" | "save_key" | "model_planner" | "model_writer" | "penyusun"> & { penyusun: [string, string][] } = {
  judul: "Penerapan Gamifikasi untuk Meningkatkan Motivasi Belajar Bahasa Arab",
  mata_kuliah: "Teknologi Pembelajaran PAI",
  dosen_pengampu: "Dr. Siti Nurhaliza, M.Pd.",
  universitas: "Islam Cendekia Nusantara",
  fakultas: "Ilmu Tarbiyah dan Keguruan",
  jurusan: "Pendidikan Agama Islam",
  kota: "Yogyakarta",
  kelas: "PAI-5B",
  tahun: "2026",
  penyusun: [["Rina Maharani", "2210511023"], ["Muhammad Iqbal Ramadhan", "2210511047"], ["Nadia Putri Lestari", "2210511058"]],
};

export function defaultForm(o: { year?: number; template?: string; provider?: string } = {}): PaperForm {
  return {
    judul: "", mata_kuliah: "", dosen_pengampu: "", penyusun: [emptyPenyusun(newRid())],
    universitas: "", fakultas: "", jurusan: "", kota: "", kelas: "", tahun: String(o.year ?? new Date().getFullYear()),
    template: o.template ?? "", mock: false, provider: o.provider ?? "openrouter", keySource: "saved",
    api_key: "", save_key: false, model_planner: "", model_writer: "",
  };
}

export function sampleForm(base: PaperForm): PaperForm {
  const { penyusun, ...rest } = SAMPLE;
  return { ...base, ...rest, penyusun: penyusun.map(([nama, nim]) => ({ rid: newRid(), nama, nim })) };
}

/** Draf yang disimpan di localStorage: TIDAK pernah memuat API key (atau pilihan simpan key). */
export function serializeDraft(f: PaperForm): string {
  const { api_key: _k, save_key: _s, ...safe } = f;
  void _k; void _s;
  return JSON.stringify(safe);
}

export function saveDraft(f: PaperForm): void { store.set(DRAFT_KEY, serializeDraft(f)); }
export function clearDraft(): void { store.remove(DRAFT_KEY); }

export function loadDraft(base: PaperForm): PaperForm | null {
  const raw = store.get(DRAFT_KEY);
  if (!raw) return null;
  try {
    const d = JSON.parse(raw) as Partial<PaperForm>;
    if (typeof d !== "object" || d === null) return null;
    const str = (v: unknown, fb: string) => (typeof v === "string" ? v : fb);
    const pen = Array.isArray(d.penyusun) && d.penyusun.length
      ? d.penyusun.slice(0, MAX_PENYUSUN).map((p) => ({ rid: newRid(), nama: str(p?.nama, ""), nim: str(p?.nim, "") }))
      : base.penyusun;
    return {
      ...base,
      judul: str(d.judul, ""), mata_kuliah: str(d.mata_kuliah, ""), dosen_pengampu: str(d.dosen_pengampu, ""),
      universitas: str(d.universitas, ""), fakultas: str(d.fakultas, ""), jurusan: str(d.jurusan, ""),
      kota: str(d.kota, ""), kelas: str(d.kelas, ""), tahun: str(d.tahun, base.tahun),
      template: str(d.template, base.template), mock: d.mock === true, provider: str(d.provider, base.provider),
      keySource: d.keySource === "new" ? "new" : "saved",
      model_planner: str(d.model_planner, ""), model_writer: str(d.model_writer, ""), penyusun: pen,
      api_key: "", save_key: false,
    };
  } catch { return null; }
}

export const isBlank = (f: PaperForm) => !f.judul.trim() && !f.mata_kuliah.trim() && !f.penyusun.some((p) => p.nama.trim());

/** Isi ulang dari job lama (tombol "Buat ulang dengan data ini"): satu kali pakai. */
export function takeRefill(base: PaperForm): PaperForm | null {
  const raw = store.get(REFILL_KEY);
  if (!raw) return null;
  store.remove(REFILL_KEY);
  try {
    const d = JSON.parse(raw) as { request?: PaperRequest; template?: string | null; mock?: boolean; provider?: string | null };
    const r = d.request;
    if (!r) return null;
    return {
      ...base,
      judul: r.judul ?? "", mata_kuliah: r.mata_kuliah ?? "", dosen_pengampu: r.dosen_pengampu ?? "",
      universitas: r.universitas ?? "", fakultas: r.fakultas ?? "", jurusan: r.jurusan ?? "", kota: r.kota ?? "", kelas: r.kelas ?? "",
      tahun: r.tahun ?? base.tahun,
      penyusun: (r.penyusun?.length ? r.penyusun : [{ nama: "" }]).slice(0, MAX_PENYUSUN).map((p) => ({ rid: newRid(), nama: p.nama ?? "", nim: p.nim ?? "" })),
      template: d.template ?? base.template, mock: d.mock === true, provider: d.provider ?? base.provider,
    };
  } catch { return null; }
}

export const providerNeedsModel = (p: ProviderInfo | undefined, id: string) => (p ? p.needs_model : id === "kenari");
