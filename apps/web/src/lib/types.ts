/** Tipe API: ditulis manual dari tabel kontrak (docs/design/HANDOFF-frontend.md bagian 4).
 *  Ganti dengan tipe hasil OpenAPI bila packages/api-types sudah ada (tugas B4). */

export type JobStatus = "queued" | "running" | "done" | "error" | "interrupted" | "cancelled";
export type StepStatus = "pending" | "running" | "done" | "skipped" | "error";
export type ProviderId = "openrouter" | "kenari";

export interface ProviderInfo {
  id: string;
  label: string;
  enabled: boolean;
  key_url: string;
  models: string[];
  default_planner: string | null;
  default_writer: string | null;
  needs_model: boolean;
}

export interface StepInfo { key: string; label: string; hint: string }

export interface AppConfig {
  hosted: boolean;
  server_key_available: boolean;
  models: unknown;
  api_key_ok: boolean;
  mock_default: boolean;
  fulltext: boolean;
  providers: ProviderInfo[];
  templates: string[];
  default_template: string;
  steps: StepInfo[];
  active_job: string | null;
  key_storage: boolean;
  auth: { mode: "clerk" | "anonymous"; required: boolean };
  daily_quota: number | null;
  year: number;
}

export interface Quota { limit: number; used: number; remaining: number; resets_at: string }
export interface Me { id: string | null; mode: "clerk" | "anonymous"; quota: Quota | null }

export interface JobSummary {
  id: string;
  status: JobStatus;
  title: string;
  created_at: string;
  finished_at?: string | null;
  mock: boolean;
  byok?: boolean;
  has_file: boolean;
  resume?: { available: boolean; done: number; total: number } | null;
  /** Opsional sampai tugas backend B1 selesai. */
  mata_kuliah?: string | null;
  progress?: { done: number; total: number } | null;
  current_step?: string | null;
  current_detail?: string;
  queue_position?: number | null;
}

export interface JobStepState { status: StepStatus; detail: string; started_at?: string | null; finished_at?: string | null }
export interface LogLine { t: string; msg: string }

export interface JobStats {
  subbab_count?: number;
  refs_found?: number;
  fulltext_ok?: number;
  fulltext_total?: number;
  citations_total?: number;
  citations_invalid_before?: number;
  citations_invalid_after?: number;
  refs_final?: number;
  refs_pruned?: number;
}

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

export interface Job extends JobSummary {
  started_at?: string | null;
  key_source?: "saved" | "session" | null;
  provider?: string | null;
  models?: { planner: string; writer: string } | null;
  resume_from?: string | null;
  template?: string | null;
  request?: PaperRequest;
  steps: Record<string, JobStepState>;
  log: LogLine[];
  error?: string | null;
  error_step?: string | null;
  usage?: { calls: number; prompt: number; completion: number; total: number } | null;
  stats?: JobStats | null;
  quota_day?: string | null;
  auto_resumed?: boolean;
  /** Opsional sampai tugas backend B2 selesai. */
  queue_position?: number | null;
}

export interface SavedKey { provider: string; saved_at: string }
export interface KeysOut { enabled: boolean; keys: SavedKey[] }

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
}

export const ACTIVE_STATUSES: JobStatus[] = ["queued", "running"];
export const isActive = (s: JobStatus) => ACTIVE_STATUSES.includes(s);
