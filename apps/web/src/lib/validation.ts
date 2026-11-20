import { z } from "zod";
import { id as t } from "../copy/id";
import type { FieldIssue } from "./api";
import type { CreateJobBody, ProviderInfo } from "./types";

/** Cermin aturan backend (apps/api: JobRequest). Ubah di sini bila backend berubah. */
export const KEY_RE = /^[\x21-\x7e]{8,300}$/;
export const MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$/;
export const YEAR_RE = /^(19|20)\d{2}$/;
export const MAX_PENYUSUN = 10;

export interface PenyusunRow { rid: string; nama: string; nim: string }

export interface PaperForm {
  judul: string; mata_kuliah: string; dosen_pengampu: string;
  penyusun: PenyusunRow[];
  universitas: string; fakultas: string; jurusan: string; kota: string; kelas: string; tahun: string;
  template: string; mock: boolean;
  provider: string; keySource: "saved" | "new";
  api_key: string; save_key: boolean;
  model_planner: string; model_writer: string;
}

export type FieldKey = "judul" | "mata_kuliah" | "penyusun" | "tahun" | "api_key" | "model_planner" | "model_writer" | "template" | "provider" | "form";
export interface FieldError { field: FieldKey; message: string; /** id elemen yang difokuskan */ anchor: string }

export const emptyPenyusun = (rid: string): PenyusunRow => ({ rid, nama: "", nim: "" });

const judulS = z.string().trim().min(3).max(200);
const mkS = z.string().trim().min(2).max(120);

export interface ValidateCtx { provider: ProviderInfo | undefined; hasSavedKey: boolean }

export function validatePaper(f: PaperForm, ctx: ValidateCtx): FieldError[] {
  const errs: FieldError[] = [];
  if (!judulS.safeParse(f.judul).success) errs.push({ field: "judul", message: t.form.err.judul, anchor: "judul" });
  if (!mkS.safeParse(f.mata_kuliah).success) errs.push({ field: "mata_kuliah", message: t.form.err.mataKuliah, anchor: "mata_kuliah" });

  const named = f.penyusun.filter((p) => p.nama.trim());
  if (!named.length) {
    errs.push({ field: "penyusun", message: t.form.err.penyusunKosong, anchor: `pn-${f.penyusun[0]?.rid ?? ""}` });
  } else {
    const orphan = f.penyusun.find((p) => !p.nama.trim() && p.nim.trim());
    if (orphan) errs.push({ field: "penyusun", message: t.form.err.nimTanpaNama, anchor: `pn-${orphan.rid}` });
    const long = named.find((p) => p.nama.trim().length > 100);
    if (long) errs.push({ field: "penyusun", message: t.form.err.namaPanjang, anchor: `pn-${long.rid}` });
  }

  if (!YEAR_RE.test(f.tahun.trim())) errs.push({ field: "tahun", message: t.form.err.tahun, anchor: "tahun" });

  if (!f.mock) {
    const kenari = f.provider === "kenari";
    if (f.keySource === "new" || !ctx.hasSavedKey) {
      const k = f.api_key.trim();
      if (k.length < 8) errs.push({ field: "api_key", message: t.form.err.keyPendek, anchor: "api_key" });
      else if (/\s/.test(k) || !KEY_RE.test(k)) errs.push({ field: "api_key", message: t.form.err.keySpasi, anchor: "api_key" });
      else if (kenari && !k.startsWith("kn-")) errs.push({ field: "api_key", message: t.form.err.keyKenari, anchor: "api_key" });
    }
    const needs = ctx.provider ? ctx.provider.needs_model : kenari;
    (["model_planner", "model_writer"] as const).forEach((k) => {
      const m = f[k].trim();
      if (!m && needs) errs.push({ field: k, message: t.form.err.modelWajib, anchor: k });
      else if (m && !MODEL_RE.test(m)) errs.push({ field: k, message: t.form.err.modelFormat, anchor: k });
    });
  }
  return errs;
}

const opt = (s: string) => (s.trim() ? s.trim() : undefined);

/** Badan POST /api/jobs. API key hanya ikut bila diisi; tidak pernah disimpan di tempat lain. */
export function buildBody(f: PaperForm, ctx: ValidateCtx): CreateJobBody {
  const body: CreateJobBody = {
    judul: f.judul.trim(),
    mata_kuliah: f.mata_kuliah.trim(),
    dosen_pengampu: opt(f.dosen_pengampu),
    penyusun: f.penyusun.filter((p) => p.nama.trim()).map((p) => ({ nama: p.nama.trim(), ...(p.nim.trim() ? { nim: p.nim.trim() } : {}) })),
    universitas: opt(f.universitas), fakultas: opt(f.fakultas), jurusan: opt(f.jurusan),
    kota: opt(f.kota), kelas: opt(f.kelas), tahun: f.tahun.trim(),
    template: f.template || undefined,
    mock: f.mock,
  };
  if (!f.mock) {
    body.provider = f.provider;
    if (opt(f.model_planner)) body.model_planner = f.model_planner.trim();
    if (opt(f.model_writer)) body.model_writer = f.model_writer.trim();
    if (f.keySource === "saved" && ctx.hasSavedKey) body.use_saved_key = true;
    else {
      body.api_key = f.api_key.trim();
      if (f.save_key) body.save_key = true;
    }
  }
  return body;
}

/** Petakan 422 backend ke kesalahan per isian (loc terakhir = nama kolom). */
export function issuesToErrors(issues: FieldIssue[], f: PaperForm): FieldError[] {
  const known: FieldKey[] = ["judul", "mata_kuliah", "penyusun", "tahun", "api_key", "model_planner", "model_writer", "template", "provider"];
  return issues.map((i) => {
    const key = i.loc.find((p) => typeof p === "string" && (known as string[]).includes(p)) as FieldKey | undefined;
    const field: FieldKey = key ?? "form";
    const anchor = field === "penyusun" ? `pn-${f.penyusun[0]?.rid ?? ""}` : field === "form" ? "judul" : field;
    return { field, message: i.msg, anchor };
  });
}
