import { describe, expect, it } from "vitest";
import { buildBody, issuesToErrors, validatePaper, type PaperForm } from "./validation";
import type { ProviderInfo } from "./types";

const kenari: ProviderInfo = { id: "kenari", label: "Kenari", enabled: true, key_url: "", models: [], default_planner: null, default_writer: null, needs_model: true };
const orouter: ProviderInfo = { id: "openrouter", label: "OpenRouter", enabled: true, key_url: "", models: [], default_planner: "a/b", default_writer: "c/d", needs_model: false };

const ok = (): PaperForm => ({
  judul: "Judul Valid", mata_kuliah: "MK", dosen_pengampu: "", subjek: "", jenjang: "", penyusun: [{ rid: "r1", nama: "Rina", nim: "" }],
  universitas: "", fakultas: "", jurusan: "", kota: "", kelas: "", tahun: "2026", template: "template makalah.docx", mock: false,
  provider: "openrouter", keySource: "new", api_key: "sk-or-v1-abcdefgh", save_key: false, model_planner: "", model_writer: "",
});
const fields = (f: PaperForm, p = orouter, saved = false) => validatePaper(f, { provider: p, hasSavedKey: saved }).map((e) => e.field);

describe("validatePaper", () => {
  it("form valid", () => expect(fields(ok())).toEqual([]));
  it("judul, mata kuliah, tahun, penyusun", () => {
    const f = { ...ok(), judul: "ab", mata_kuliah: "x", tahun: "1899", penyusun: [{ rid: "r", nama: " ", nim: "" }] };
    expect(fields(f).sort()).toEqual(["judul", "mata_kuliah", "penyusun", "tahun"]);
  });
  it("NIM tanpa nama ditolak", () => {
    const f = { ...ok(), penyusun: [{ rid: "a", nama: "A", nim: "" }, { rid: "b", nama: "", nim: "123" }] };
    expect(fields(f)).toEqual(["penyusun"]);
  });
  it("key: terlalu pendek, spasi, kn- untuk Kenari", () => {
    expect(fields({ ...ok(), api_key: "pendek" })).toEqual(["api_key"]);
    expect(fields({ ...ok(), api_key: "ada spasi disini" })).toEqual(["api_key"]);
    const k = { ...ok(), provider: "kenari", model_planner: "m:free", model_writer: "m:free" };
    expect(fields({ ...k, api_key: "sk-bukan-kenari" }, kenari)).toEqual(["api_key"]);
    expect(fields({ ...k, api_key: "kn-abcdefgh" }, kenari)).toEqual([]);
  });
  it("Kenari wajib model; id model dicek polanya", () => {
    expect(fields({ ...ok(), provider: "kenari", api_key: "kn-abcdefgh" }, kenari).sort()).toEqual(["model_planner", "model_writer"]);
    expect(fields({ ...ok(), model_planner: "-salah" })).toEqual(["model_planner"]);
  });
  it("key tersimpan tidak perlu isi key; Mode uji melewati bagian key", () => {
    expect(fields({ ...ok(), keySource: "saved", api_key: "" }, orouter, true)).toEqual([]);
    expect(fields({ ...ok(), mock: true, api_key: "" })).toEqual([]);
  });
});

describe("buildBody", () => {
  it("memangkas isian kosong; key hanya bila dipakai", () => {
    const b = buildBody({ ...ok(), save_key: true, penyusun: [{ rid: "a", nama: " Rina ", nim: "" }, { rid: "b", nama: "", nim: "" }] }, { provider: orouter, hasSavedKey: false });
    expect(b.penyusun).toEqual([{ nama: "Rina" }]);
    expect(b).toMatchObject({ api_key: "sk-or-v1-abcdefgh", save_key: true, provider: "openrouter", mock: false });
    expect(b.dosen_pengampu).toBeUndefined();
  });
  it("key tersimpan -> use_saved_key tanpa api_key; Mode uji -> tanpa key/provider", () => {
    const s = buildBody({ ...ok(), keySource: "saved", api_key: "" }, { provider: orouter, hasSavedKey: true });
    expect(s.use_saved_key).toBe(true);
    expect(s.api_key).toBeUndefined();
    const m = buildBody({ ...ok(), mock: true }, { provider: orouter, hasSavedKey: false });
    expect(m.api_key).toBeUndefined();
    expect(m.provider).toBeUndefined();
  });
});

describe("issuesToErrors", () => {
  it("memetakan loc 422 ke isian", () => {
    const es = issuesToErrors([{ loc: ["body", "judul"], type: "x", msg: "salah" }, { loc: ["body", "aneh"], type: "x", msg: "lain" }], ok());
    expect(es.map((e) => e.field)).toEqual(["judul", "form"]);
  });
});

describe("lingkup opsional (subjek/jenjang)", () => {
  it("ikut ke badan hanya bila diisi", () => {
    const ctx = { provider: undefined, hasSavedKey: false };
    expect(buildBody({ ...ok(), subjek: "  siswa MTs ", jenjang: "MTs" }, ctx)).toMatchObject({ subjek: "siswa MTs", jenjang: "MTs" });
    const kosong = buildBody(ok(), ctx);
    expect(kosong.subjek).toBeUndefined();
    expect(kosong.jenjang).toBeUndefined();
  });
});
