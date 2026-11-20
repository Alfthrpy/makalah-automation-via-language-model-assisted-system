/* Cek state khusus dengan API dicegat (tanpa backend) + audit axe pada tiap layar.
 *   pnpm --filter web dev   (proxy /api tidak dipakai; semua /api dicegat)
 *   NODE_PATH=$(npm root -g) node apps/web/e2e/states.cjs [baseURL] [shotDir]            */
const { chromium } = require("playwright");
const path = require("path");
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const SHOTS = process.argv[3] || "";
const axePath = require.resolve("axe-core", { paths: [path.join(__dirname, "..")] });
const must = (c, m) => { if (!c) throw new Error("GAGAL: " + m); console.log("ok:", m); };
const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

const STEPS = ["input", "outline", "fulltext", "tulis", "sitasi", "pengantar", "docx"];
const CONFIG = {
  hosted: false, server_key_available: false, models: null, api_key_ok: false, mock_default: false, fulltext: true,
  providers: [
    { id: "openrouter", label: "OpenRouter", enabled: true, key_url: "https://openrouter.ai/keys", models: ["deepseek/deepseek-v3.2", "google/gemini-2.5-flash"], default_planner: "deepseek/deepseek-v3.2", default_writer: "google/gemini-2.5-flash", needs_model: false },
    { id: "kenari", label: "Kenari", enabled: true, key_url: "https://kenari.id", models: ["step-3-7-flash:free"], default_planner: null, default_writer: null, needs_model: true },
  ],
  templates: ["template makalah.docx", "template makalah2.docx"], default_template: "template makalah.docx",
  steps: STEPS.map((k, i) => ({ key: k, label: ["Memuat data", "Outline & referensi", "Full-text referensi", "Menulis sub-bab", "Verifikasi sitasi", "Kata pengantar", "Membuat dokumen"][i], hint: "Petunjuk tahap" })),
  active_job: null, key_storage: true, auth: { mode: "anonymous", required: false }, daily_quota: 3, year: 2026,
};
const REQ = { judul: "Peran Kecerdasan Buatan dalam Pembelajaran Fiqih", mata_kuliah: "Fiqih Kontemporer", penyusun: [{ nama: "Rina" }], tahun: "2026" };
const now = new Date().toISOString();
const mkSteps = (m) => Object.fromEntries(STEPS.map((k, i) => [k, m(i)]));
const JOB = (status, extra = {}) => ({
  id: "j" + status, status, title: REQ.judul, created_at: now, started_at: now, finished_at: null, mock: false, byok: true, key_source: "saved",
  provider: "openrouter", models: { planner: "deepseek/deepseek-v3.2", writer: "google/gemini-2.5-flash" }, template: "template makalah.docx", request: REQ,
  steps: mkSteps(() => ({ status: "pending", detail: "" })), log: [{ t: now, msg: "input mulai" }], error: null, error_step: null, usage: null, stats: null, has_file: false, resume: null, ...extra,
});
const JOBS = {
  queued: JOB("queued", { queue_position: 2 }),
  running: JOB("running", { steps: mkSteps((i) => i < 3 ? { status: "done", detail: "ok", started_at: now, finished_at: now } : i === 3 ? { status: "running", detail: "4/11 · 2.1 Konsep" } : { status: "pending", detail: "" }) }),
  error: JOB("error", { error: "Penyedia menolak permintaan: kredit tidak cukup (402).", error_step: "tulis", finished_at: now, resume: { available: true, done: 6, total: 11 },
    steps: mkSteps((i) => i < 3 ? { status: "done", detail: "ok" } : i === 3 ? { status: "error", detail: "6/11" } : { status: "pending", detail: "" }) }),
  interrupted: JOB("interrupted", { key_source: "session", resume: { available: true, done: 3, total: 9 }, finished_at: now }),
  cancelled: JOB("cancelled", { finished_at: now }),
};
const SUMMARY = (j) => ({ id: j.id, status: j.status, title: j.title, created_at: j.created_at, finished_at: j.finished_at, mock: false, byok: true, has_file: false, resume: j.resume, mata_kuliah: "Fiqih Kontemporer", progress: j.status === "running" ? { done: 3, total: 7 } : null, current_step: j.status === "running" ? "tulis" : null, current_detail: "4/11 · 2.1 Konsep", queue_position: j.queue_position ?? null });

async function mock(p, { jobs = Object.values(JOBS), me = { id: null, mode: "anonymous", quota: { limit: 3, used: 1, remaining: 2, resets_at: new Date(Date.now() + 7 * 3600e3).toISOString() } }, post } = {}) {
  await p.route("**/api/**", (route) => {
    const u = new URL(route.request().url()); const m = route.request().method();
    if (u.pathname === "/api/config") return json(route, CONFIG);
    if (u.pathname === "/api/me") return json(route, me);
    if (u.pathname === "/api/keys") return json(route, { enabled: true, keys: [{ provider: "openrouter", saved_at: now }] });
    if (u.pathname === "/api/jobs" && m === "GET") return json(route, jobs.map(SUMMARY));
    if (u.pathname === "/api/jobs" && m === "POST") return post ? post(route) : json(route, JOB("queued"), 202);
    const mm = /^\/api\/jobs\/(.+)$/.exec(u.pathname);
    if (mm && m === "GET") { const j = JOBS[mm[1].replace(/^j/, "")]; return j ? json(route, j) : json(route, { detail: "Job tidak ditemukan" }, 404); }
    return json(route, { detail: "?" }, 404);
  });
}
const axe = async (p, where) => {
  await p.addScriptTag({ path: axePath });
  const r = await p.evaluate(async () => (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] })).violations.map((v) => ({ id: v.id, n: v.nodes.length, impact: v.impact, ex: v.nodes[0].target.join(" ") + " | " + (v.nodes[0].failureSummary || "").split("\n").slice(0, 3).join(" ") })));
  if (r.length) { console.log("AXE", where, JSON.stringify(r, null, 1)); }
  return r;
};

(async () => {
  const b = await chromium.launch(); const errs = []; let axeBad = 0;
  for (const [w, h, scheme] of [[1280, 900, "light"], [390, 844, "dark"]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce" });
    const p = await ctx.newPage();
    p.on("console", (m) => { if (m.type() === "error" && !/status of (404|429|401)/.test(m.text())) errs.push(`${w}: ${m.text()}`); });
    p.on("pageerror", (e) => errs.push(`${w} pageerror: ${e.message}`));
    await mock(p);
    await p.addInitScript(() => localStorage.setItem("malas.dev.signedin", "1"));
    const shot = (n) => SHOTS && p.screenshot({ path: `${SHOTS}/${n}-${w}.png`, fullPage: true });
    const noOv = async (n) => must((await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 0, `${w}px tanpa overflow: ${n}`);

    await p.goto(BASE + "/dasbor"); await p.getByRole("link", { name: /Lihat progres/ }).first().waitFor();
    await noOv("dasbor"); await shot("s-dasbor"); axeBad += (await axe(p, "dasbor " + w)).length;
    for (const st of ["queued", "running", "error", "interrupted", "cancelled"]) {
      await p.goto(`${BASE}/job/j${st}`); await p.getByRole("heading", { level: 1 }).waitFor();
      await p.getByText(/Progres/).first().waitFor(); await noOv("job " + st); await shot("s-job-" + st);
      axeBad += (await axe(p, `job ${st} ${w}`)).length;
    }
    // dialog lanjutkan (key tersimpan)
    await p.goto(`${BASE}/job/jerror`);
    await p.getByRole("button", { name: /Lanjutkan dari titik terakhir/ }).click();
    await p.getByRole("dialog").getByText("Pakai key OpenRouter tersimpan").waitFor(); await shot("s-resume");
    await p.keyboard.press("Escape");
    // buat: validasi + 429
    await p.goto(BASE + "/buat"); await p.getByRole("heading", { name: "Buat makalah", level: 1 }).waitFor();
    await p.getByText("Satu makalah masih diproses").waitFor();
    // ada job aktif -> tombol nonaktif dengan alasan
    must((await p.getByText("Tunggu makalah yang sedang diproses selesai.").locator("visible=true").count()) > 0, "tombol kirim nonaktif ada alasan (job aktif)");
    await noOv("buat"); await shot("s-buat-aktif"); axeBad += (await axe(p, "buat " + w)).length;
    await p.goto(BASE + "/pengaturan"); await p.getByText("Tersimpan terenkripsi").waitFor(); await shot("s-pengaturan"); axeBad += (await axe(p, "pengaturan " + w)).length;
    await p.getByRole("button", { name: "Hapus key" }).click(); await p.getByRole("dialog").getByText(/dihapus permanen/).waitFor(); await shot("s-hapus-key");
    await ctx.close();

    // tanpa job aktif: validasi klien + 429 kuota/antrean + 401
    const c2 = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce" }); const q = await c2.newPage();
    q.on("pageerror", (e) => errs.push(`${w} pageerror: ${e.message}`));
    await mock(q, { jobs: [JOBS.cancelled], post: (r) => json(r, { detail: "Antrean penuh. Coba lagi beberapa menit lagi." }, 429) });
    await q.addInitScript(() => localStorage.setItem("malas.dev.signedin", "1"));
    await q.goto(BASE + "/buat"); await q.getByRole("heading", { name: "Buat makalah", level: 1 }).waitFor();
    await q.getByRole("button", { name: "Buat makalah" }).last().click({ force: true });
    await q.getByText(/isian perlu diperbaiki/).waitFor();
    must(await q.evaluate(() => document.activeElement && document.activeElement.id) === "judul", "fokus pindah ke isian pertama yang salah");
    if (SHOTS) await q.screenshot({ path: `${SHOTS}/s-validasi-${w}.png`, fullPage: true });
    await q.getByRole("button", { name: "Isi contoh" }).click();
    await q.getByLabel(/Masukkan key lain/).check();
    await q.getByLabel(/API key OpenRouter/).fill("sk-or-v1-abcdefgh12345");
    await q.getByRole("button", { name: "Buat makalah" }).last().click({ force: true });
    await q.getByText("Antrean sedang penuh").waitFor(); must(true, "429 antrean penuh -> banner");
    const ls = await q.evaluate(() => JSON.stringify(Object.entries(localStorage)));
    must(!ls.includes("sk-or-v1"), "API key TIDAK ada di localStorage (draf)");
    must((await q.evaluate(() => sessionStorage.length)) === 0, "sessionStorage kosong");
    await q.unroute("**/api/**"); await mock(q, { jobs: [] });
    await q.route("**/api/jobs", (r) => r.request().method() === "GET" ? json(r, { detail: "Silakan masuk terlebih dahulu." }, 401) : r.fallback());
    await q.goto(BASE + "/dasbor"); await q.getByRole("dialog").getByText("Sesi kamu berakhir").waitFor(); must(true, "401 -> dialog sesi berakhir"); await shot2(q, "s-401");
    await c2.close();
    const c3 = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme }); const d = await c3.newPage();
    await d.route("**/api/**", (r) => json(r, { detail: "x" }, 503));
    await d.goto(BASE + "/"); await d.getByText("Server belum merespons").waitFor(); must(true, "config 5xx -> banner server tidak bisa dihubungi");
    await shot2(d, "s-server-down"); await c3.close();
    function shot2(pg, n) { return SHOTS ? pg.screenshot({ path: `${SHOTS}/${n}-${w}.png` }) : null; }
  }
  await b.close();
  if (errs.length) { console.log("ERROR KONSOL:\n" + errs.join("\n")); process.exit(1); }
  console.log(axeBad ? `SELESAI, tapi ada ${axeBad} pelanggaran axe` : "SEMUA LULUS, 0 error konsol, 0 pelanggaran axe");
  process.exit(axeBad ? 2 : 0);
})().catch((e) => { console.error(e.message); process.exit(1); });
