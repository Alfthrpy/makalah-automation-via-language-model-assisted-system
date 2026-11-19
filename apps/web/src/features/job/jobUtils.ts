import type { AppConfig, Job, JobStepState, JobSummary, StepInfo } from "../../lib/types";

/** Tahap bawaan bila /api/config belum termuat (kunci sama dengan backend). */
export const FALLBACK_STEPS: StepInfo[] = [
  { key: "input", label: "Memuat data", hint: "Membaca data makalah dan penyusun" },
  { key: "outline", label: "Outline & referensi", hint: "Menyusun bab/sub-bab dan mencari referensi akademik" },
  { key: "fulltext", label: "Full-text referensi", hint: "Mengunduh isi paper open-access (tanpa LLM)" },
  { key: "tulis", label: "Menulis sub-bab", hint: "Menulis isi tiap sub-bab dengan sitasi APA" },
  { key: "sitasi", label: "Verifikasi sitasi", hint: "Mencocokkan sitasi dengan daftar pustaka" },
  { key: "pengantar", label: "Kata pengantar", hint: "Menulis kata pengantar" },
  { key: "docx", label: "Membuat dokumen", hint: "Merender ke template Word (.docx)" },
];

export const stepsOf = (cfg?: AppConfig): StepInfo[] => (cfg?.steps?.length ? cfg.steps : FALLBACK_STEPS);
export const stepLabel = (steps: StepInfo[], key?: string | null) => steps.find((s) => s.key === key)?.label ?? "";

/** Persentase kasar dari ringkasan riwayat: tahap selesai + setengah untuk yang berjalan. */
export function summaryPct(j: JobSummary): number {
  const p = j.progress;
  if (!p || !p.total) return 0;
  return Math.min(100, Math.round(((p.done + (j.current_step ? 0.5 : 0)) / p.total) * 100));
}

/** Persentase dari detail job (steps). */
export function jobPct(job: Job, steps: StepInfo[]): number {
  let done = 0, running = 0;
  for (const s of steps) {
    const st = job.steps[s.key]?.status;
    if (st === "done" || st === "skipped") done++;
    else if (st === "running") running = 0.5;
  }
  return Math.round(((done + running) / (steps.length || 1)) * 100);
}

export function stepSeconds(s?: JobStepState): number | null {
  if (!s?.started_at || !s.finished_at) return null;
  const d = (new Date(s.finished_at).getTime() - new Date(s.started_at).getTime()) / 1000;
  return Number.isFinite(d) && d >= 0 ? d : null;
}

export function elapsedLabel(startIso?: string | null, endIso?: string | null, now = Date.now()): string {
  if (!startIso) return "";
  const end = endIso ? new Date(endIso).getTime() : now;
  const sec = Math.max(0, Math.round((end - new Date(startIso).getTime()) / 1000));
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m} mnt ${String(s).padStart(2, "0")} dtk`;
}

export function currentStepKey(job: Job): string | null {
  return Object.entries(job.steps).find(([, v]) => v.status === "running")?.[0] ?? null;
}
export function errorStepKey(job: Job, steps: StepInfo[]): string | null {
  return job.error_step ?? steps.find((s) => job.steps[s.key]?.status === "error")?.key ?? null;
}
