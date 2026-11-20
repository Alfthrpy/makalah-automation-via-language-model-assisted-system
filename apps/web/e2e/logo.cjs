/* E2E logo kampus/sekolah lewat UI asli + backend sungguhan (mode anonim, Mode uji):
 *   uv run malas-web   &   pnpm --filter web dev
 *   NODE_PATH=$(npm root -g) node apps/web/e2e/logo.cjs [baseURL]
 * Membuktikan: validasi tipe di klien, unggah + pratinjau, logo benar-benar tertanam di .docx hasil (dan tidak
 * tertanam bila opsinya dimatikan), hapus dari Pengaturan, serta aksesibilitas (axe) dan tanpa overflow/error konsol. */
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { execFileSync } = require("child_process");
const BASE = process.argv[2] || "http://127.0.0.1:5173";
const axePath = require.resolve("axe-core", { paths: [path.join(__dirname, "..")] });
const must = (c, m) => { if (!c) throw new Error("GAGAL: " + m); console.log("ok:", m); };
const media = (docx) => execFileSync("unzip", ["-p", docx, "word/media/image1.png"], { maxBuffer: 20e6 });

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "logo-e2e-"));
  const b = await chromium.launch();
  const errs = [];
  for (const [w, h] of [[390, 844], [1280, 900]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, reducedMotion: "reduce", acceptDownloads: true });
    const p = await ctx.newPage();
    p.on("console", (m) => { if (m.type() === "error" && !/status of 404/.test(m.text())) errs.push(`${w}: ${m.text()}`); });
    p.on("pageerror", (e) => errs.push(`${w} pageerror: ${e.message}`));
    const noOverflow = async (where) => must((await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)) <= 0, `${w}px tanpa overflow di ${where}`);
    const axe = async (where) => {
      await p.addScriptTag({ path: axePath });
      const v = await p.evaluate(async () => (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] })).violations.map((x) => x.id + "(" + x.nodes.length + ")"));
      must(v.length === 0, `${w}px axe 0 pelanggaran di ${where}${v.length ? " :: " + v.join(",") : ""}`);
    };

    await p.goto(BASE + "/masuk"); await p.getByRole("button", { name: /Lanjut sebagai pengguna lokal/ }).click();
    await p.getByRole("heading", { name: /Selamat/ }).waitFor();
    await p.goto(BASE + "/buat"); await p.getByRole("heading", { name: "Buat makalah", level: 1 }).waitFor();
    await p.getByText("Belum ada logo tersimpan.").waitFor();
    must(true, "awalnya belum ada logo");

    // berkas bukan gambar -> ditolak di klien dengan pesan jelas
    const fileInput = p.locator("#create-logo-file");
    await fileInput.setInputFiles({ name: "x.png", mimeType: "image/svg+xml", buffer: Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'/>") });
    await p.getByRole("alert").filter({ hasText: "PNG atau JPEG" }).waitFor();
    must(true, "SVG ditolak dengan pesan jelas");

    // foto besar (1600x900 JPEG) -> diperkecil jadi PNG persegi lalu tersimpan
    const jpeg = await p.evaluate(async () => {
      const c = document.createElement("canvas"); c.width = 1600; c.height = 900; const x = c.getContext("2d");
      x.fillStyle = "#c81e1e"; x.fillRect(0, 0, 1600, 900); x.fillStyle = "#ffffff"; x.fillRect(600, 250, 400, 400);
      const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9)); return Array.from(new Uint8Array(await blob.arrayBuffer()));
    });
    await fileInput.setInputFiles({ name: "logo.jpg", mimeType: "image/jpeg", buffer: Buffer.from(jpeg) });
    await p.getByRole("img", { name: /Pratinjau logo/ }).waitFor();
    must(await p.locator("#use_logo").isChecked(), "logo tersimpan; opsi 'pakai di sampul' aktif otomatis");
    await noOverflow("buat (dengan logo)"); await axe("buat (dengan logo)");

    const stored = Buffer.from(await p.evaluate(async () => Array.from(new Uint8Array(await (await fetch("/api/logo")).arrayBuffer()))));
    must(stored.subarray(0, 4).toString("hex") === "89504e47" && stored.readUInt32BE(16) === 600 && stored.readUInt32BE(20) === 600, "logo di server = PNG 600x600");

    async function buatDanUnduh(nama) {
      await p.getByRole("button", { name: "Isi contoh" }).click();
      await p.getByLabel(/Mode uji/).check();
      await p.getByRole("button", { name: "Buat makalah" }).last().click();
      await p.waitForURL(/\/job\//);
      await p.getByRole("heading", { name: "Makalah siap" }).waitFor({ timeout: 90000 });
      const [dl] = await Promise.all([p.waitForEvent("download"), p.getByRole("button", { name: /Unduh \.docx/ }).click()]);
      const f = path.join(tmp, `${nama}-${w}.docx`); await dl.saveAs(f); return f;
    }

    const adaLogo = await buatDanUnduh("dengan");
    must(Buffer.compare(media(adaLogo), stored) === 0, "docx hasil memuat logo pengguna (byte-identik dengan yang tersimpan)");

    await p.goto(BASE + "/buat"); await p.getByRole("heading", { name: "Buat makalah", level: 1 }).waitFor();
    await p.locator("#use_logo").uncheck();
    const tanpa = await buatDanUnduh("tanpa");
    const m2 = media(tanpa);
    must(Buffer.compare(m2, stored) !== 0 && m2.subarray(0, 4).toString("hex") === "89504e47", "tanpa opsi logo: sampul memakai penanda netral (bukan logo pengguna)");

    await p.goto(BASE + "/pengaturan"); await p.getByRole("heading", { name: "Pengaturan", level: 1 }).waitFor();
    await p.getByRole("img", { name: /Pratinjau logo/ }).waitFor();
    await noOverflow("pengaturan"); await axe("pengaturan");
    await p.getByRole("button", { name: "Hapus logo" }).click();
    await p.getByRole("dialog").getByRole("button", { name: "Hapus logo" }).click();
    await p.getByText("Belum ada logo tersimpan.").waitFor();
    must((await p.evaluate(async () => (await fetch("/api/logo")).status)) === 404, "logo terhapus di server");
    await ctx.close();
  }
  await b.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  if (errs.length) { console.log("ERROR KONSOL:\n" + errs.join("\n")); process.exit(1); }
  console.log("SEMUA LULUS, 0 error konsol");
})().catch((e) => { console.error(e.message); process.exit(1); });
