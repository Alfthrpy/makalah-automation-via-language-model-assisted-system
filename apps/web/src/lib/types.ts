import type { components } from "@malas/api-types";

/** Tipe API: dihasilkan dari OpenAPI backend (packages/api-types, `pnpm --filter @malas/api-types generate`).
 *  Jangan menulis ulang bentuk respons di sini; ubah model di apps/api/src/malas_api/schemas.py lalu generate ulang. */
type S = components["schemas"];

export type JobStatus = S["JobSummary"]["status"];
export type StepStatus = S["JobStep"]["status"];
export type ProviderId = "openrouter" | "kenari";

export type ProviderInfo = S["ProviderInfo"];
export type StepInfo = S["StepInfo"];
export type AppConfig = S["ConfigOut"];
export type Quota = S["Quota"];
export type Me = S["MeOut"];
export type JobSummary = S["JobSummary"];
export type JobStepState = S["JobStep"];
export type LogLine = S["LogLine"];
export type JobStats = S["JobStats"];
/** Data makalah yang tersimpan di job (respons). */
export type PaperRequestOut = S["PaperRequest"];
export type Job = S["JobOut"];
export type SavedKey = S["SavedKey"];
export type KeysOut = S["KeysOut"];

/** Input form (BUKAN dari OpenAPI: skema JobRequest menandai field ber-default sebagai wajib, padahal opsional bagi klien).
 *  Cermin `JobRequest` di apps/api/src/malas_api/app.py; validasi sisi klien ada di validation.ts. */
export interface Penyusun { nama: string; nim?: string }

export interface PaperRequest {
  judul: string;
  mata_kuliah: string;
  dosen_pengampu?: string;
  penyusun: Penyusun[];
  kelas?: string;
  universitas?: string;
  fakultas?: string;
  jurusan?: string;
  kota?: string;
  tahun?: string;
}

/** Badan POST /api/jobs (hanya yang dipakai web). */
export interface CreateJobBody extends PaperRequest {
  template?: string;
  mock?: boolean;
  provider?: string;
  api_key?: string;
  model_planner?: string;
  model_writer?: string;
  resume_from?: string;
  save_key?: boolean;
  use_saved_key?: boolean;
  use_logo?: boolean;
}

export const ACTIVE_STATUSES: JobStatus[] = ["queued", "running"];
export const isActive = (s: JobStatus) => ACTIVE_STATUSES.includes(s);
