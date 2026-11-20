// Render video promo MALAS v6 ("5 Tahap Duka Ngerjain Makalah") per bingkai (deterministik) -> malas-promo-v6-silent.mp4 + events.json (untuk audio.py).
// Biasanya dipanggil lewat build.sh. Langsung:  NODE_PATH=$(npm root -g) node marketing/video/v6/render.cjs
// Opsi env: FRAMES_DIR (folder sementara), KEEP_FRAMES=1 (jangan hapus bingkai)
// Keluaran: malas-promo-v6-silent.mp4, events.json, contact-sheet.png (bersih), contact-sheet-safezone.png (dengan zona aman),
//           legibility-360.png (bingkai diperkecil ke lebar 360px untuk uji keterbacaan).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const DIR = __dirname;
const FRAMES = process.env.FRAMES_DIR ||
  '/tmp/claude-0/-home-user-makalah-automation-via-language-model-assisted-system/b78ce773-e104-5c40-bac3-a14889c65b22/scratchpad/frames-v6';
const OUT = path.join(DIR, 'malas-promo-v6-silent.mp4');
const fname = (i) => path.join(FRAMES, String(i).padStart(5, '0') + '.png');

async function sheet(page, picks, fps, file, { w, h, safe, cols }) {
  const cells = picks.map((f) => `<figure><div class="f"><img src="file://${fname(f)}">${safe ? '<i class="t"></i><i class="b"></i><i class="r"></i>' : ''}</div>
    <figcaption>#${f} &middot; ${(f / fps).toFixed(2)} dtk</figcaption></figure>`).join('');
  const rows = Math.ceil(picks.length / cols);
  await page.setViewportSize({ width: cols * w + (cols + 1) * 12, height: rows * (h + 34) + (rows + 1) * 12 });
  const k = w / 1080;
  await page.setContent(`<style>
    body{margin:0;background:#1b1d24;font:600 16px monospace;color:#ddd}
    .g{display:grid;grid-template-columns:repeat(${cols},${w}px);gap:12px;padding:12px}
    figure{margin:0}.f{position:relative;width:${w}px;height:${h}px;overflow:hidden}
    img{width:${w}px;height:${h}px;display:block}
    i{position:absolute;background:rgba(255,0,60,.22);outline:1px dashed rgba(255,0,60,.85)}
    .t{left:0;right:0;top:0;height:${250 * k}px}.b{left:0;right:0;bottom:0;height:${380 * k}px}.r{top:0;bottom:0;right:0;width:${120 * k}px}
    figcaption{height:30px;line-height:30px}</style><div class="g">${cells}</div>`);
  await page.waitForFunction(() => Array.from(document.images).every((im) => im.complete && im.naturalWidth));
  await page.screenshot({ path: path.join(DIR, file), fullPage: true });
}

(async () => {
  fs.rmSync(FRAMES, { recursive: true, force: true });
  fs.mkdirSync(FRAMES, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.route(/^https?:/, (r) => r.abort()); // tanpa internet: semua aset lokal
  await page.goto('file://' + path.join(DIR, 'index.html'));
  const fontsOk = await page.evaluate(() => window.__ready);
  if (!fontsOk) throw new Error('Font belum termuat; batal render.');
  const { dur, fps } = await page.evaluate(() => ({ dur: window.DURATION_MS, fps: window.FPS }));
  const n = Math.round((dur / 1000) * fps);
  const tl = await page.evaluate(() => ({ timeline: window.TIMELINE, events: window.EVENTS, frames: Math.round(window.DURATION_MS / 1000 * window.FPS), fps: window.FPS }));
  fs.writeFileSync(path.join(DIR, 'events.json'), JSON.stringify(tl, null, 1));
  const stage = await page.$('#stage');
  console.log(`Render ${n} bingkai @${fps}fps ke ${FRAMES}`);
  for (let i = 0; i < n; i++) {
    await page.evaluate((t) => window.renderFrame(t), (i * 1000) / fps);
    await stage.screenshot({ path: fname(i) });
    if (i % 90 === 0) console.log(`  ${i}/${n}`);
  }
  if (errors.length) throw new Error('Error di halaman: ' + errors.join(' | '));

  // bingkai pilihan: satu-dua per adegan, di keadaan diam (bukan di tengah transisi)
  // satu-dua bingkai per tahap (hook, T1-T5, tercapai, CTA-a, CTA-b)
  const secs = [0.5, 1.9, 8.0, 12.5, 20.0, 24.0, 30.0, 36.5, 41.0, 45.0, 52.0, 60.0, 64.5, 68.9, 72.3, 74.9];
  const picks = secs.map((s) => Math.round(s * fps));
  await sheet(page, picks, fps, 'contact-sheet.png', { w: 270, h: 480, safe: false, cols: 4 });
  await sheet(page, picks, fps, 'contact-sheet-safezone.png', { w: 270, h: 480, safe: true, cols: 4 });
  await sheet(page, picks, fps, 'legibility-360.png', { w: 360, h: 640, safe: false, cols: 4 });
  await browser.close();

  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(FRAMES, '%05d.png'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(fps),
    '-movflags', '+faststart', OUT], { stdio: 'inherit' });
  if (!process.env.KEEP_FRAMES) fs.rmSync(FRAMES, { recursive: true, force: true });
  console.log('Selesai:', OUT, (fs.statSync(OUT).size / 1e6).toFixed(2) + ' MB');
})().catch((e) => { console.error(e); process.exit(1); });
