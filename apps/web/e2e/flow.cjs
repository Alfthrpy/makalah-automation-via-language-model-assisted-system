/* E2E alur utama terhadap backend sungguhan (mode anonim + Mode uji).
 *   uv run malas-web   &   pnpm --filter web dev
 *   NODE_PATH=$(npm root -g) node apps/web/e2e/flow.cjs [baseURL] [shotDir]
 * Playwright sudah terpasang di sandbox (jangan `playwright install`). */
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const SHOTS = process.argv[3] || "";
const must = (c, m) => { if (!c) throw new Error("GAGAL: " + m); console.log("ok:", m); };

(async () => {
  const b = await chromium.launch();
  const errs = [];
  for (const [w, h, scheme] of [[1280, 900, "light"], [390, 844, "dark"]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce", acceptDownloads: true });
    const p = await ctx.newPage();
    p.on("console", (m) => { if (m.type() === "error" && !/status of 404/.test(m.text())) errs.push(`${w}: ${m.text()}`); });
    p.on("pageerror", (e) => errs.push(`${w} pageerror: ${e.message}`));
    const shot = (n) => SHOTS && p.screenshot({ path: `${SHOTS}/${n}-${w}.png`, fullPage: true });
    const noOverflow = async (where) => must((await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 0, `${w}px tanpa overflow horizontal di ${where}`);

    await p.goto(BASE + "/"); await p.getByRole("heading", { level: 1 }).waitFor();
    await noOverflow("landing");
    await p.getByRole("link", { name: "Masuk" }).first().click();
    await p.getByRole("button", { name: /Lanjut sebagai pengguna lokal/ }).click();
    await p.getByRole("heading", { name: /Selamat/ }).waitFor();
    must(p.url().endsWith("/dasbor"), "masuk -> /dasbor");
    await noOverflow("dasbor"); await shot("dasbor-kosong");

    await p.getByRole("link", { name: /Buat makalah/ }).first().click();
    await p.getByRole("heading", { name: "Buat makalah", level: 1 }).waitFor();
    await p.getByRole("button", { name: "Isi contoh" }).click();
    await p.getByLabel(/Mode uji/).check();
    await noOverflow("buat"); await shot("buat");
    await p.getByRole("button", { name: "Buat makalah" }).last().click();
    await p.waitForURL(/\/job\//);
    await p.getByRole("heading", { name: "Makalah siap" }).waitFor({ timeout: 60000 });
    must(true, "job mode uji selesai");
    await noOverflow("job"); await shot("job-selesai");
    const [dl] = await Promise.all([p.waitForEvent("download"), p.getByRole("button", { name: /Unduh \.docx/ }).click()]);
    const path = await dl.path();
    const head = require("fs").readFileSync(path).subarray(0, 2).toString();
    must(head === "PK", "unduhan .docx valid (PK)");

    await p.getByRole("link", { name: "Riwayat" }).click();
    await p.getByRole("link", { name: /Gamifikasi/ }).waitFor();
    must(true, "riwayat memuat job");
    await noOverflow("dasbor berisi");
    await p.goto(BASE + "/pengaturan"); await p.getByRole("heading", { name: "Pengaturan", level: 1 }).waitFor();
    await noOverflow("pengaturan"); await shot("pengaturan");
    await p.goto(BASE + "/tidak-ada"); await p.getByText("Halaman tidak ditemukan").waitFor();
    await p.goto(BASE + "/job/abc123"); await p.getByText("Makalah ini tidak ditemukan").waitFor();
    must(true, "404 halaman & job");
    await ctx.close();
  }
  await b.close();
  if (errs.length) { console.log("ERROR KONSOL:\n" + errs.join("\n")); process.exit(1); }
  console.log("SEMUA LULUS, 0 error konsol");
})().catch((e) => { console.error(e.message); process.exit(1); });
