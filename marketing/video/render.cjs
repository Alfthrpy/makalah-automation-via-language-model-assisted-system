// Render video promo MALAS per bingkai (deterministik) lalu encode ke H.264.
// Jalankan:  NODE_PATH=$(npm root -g) node render.cjs
// Opsi env:  FRAMES_DIR (folder sementara), KEEP_FRAMES=1 (jangan hapus bingkai)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const DIR = __dirname;
const FRAMES = process.env.FRAMES_DIR ||
  '/tmp/claude-0/-home-user-makalah-automation-via-language-model-assisted-system/14c6514b-4599-4eb5-bff7-fe613c78f5ef/scratchpad/frames';
const OUT = path.join(DIR, 'malas-promo.mp4');
const SHEET = path.join(DIR, 'contact-sheet.png');

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
  const stage = await page.$('#stage');
  console.log(`Render ${n} bingkai @${fps}fps ke ${FRAMES}`);
  for (let i = 0; i < n; i++) {
    await page.evaluate((t) => window.renderFrame(t), (i * 1000) / fps);
    await stage.screenshot({ path: path.join(FRAMES, String(i).padStart(5, '0') + '.png') });
    if (i % 60 === 0) console.log(`  ${i}/${n}`);
  }
  if (errors.length) throw new Error('Error di halaman: ' + errors.join(' | '));

  // contact sheet: 16 bingkai + garis safe zone TikTok/Reels (atas 250, bawah 380, kanan 120)
  const picks = Array.from({ length: 16 }, (_, k) => Math.min(n - 1, Math.round((k * (n - 1)) / 15)));
  const cells = picks.map((f) => `<figure><div class="f"><img src="file://${path.join(FRAMES, String(f).padStart(5, '0') + '.png')}">
    <i class="t"></i><i class="b"></i><i class="r"></i></div><figcaption>#${f} &middot; ${(f / fps).toFixed(2)} dtk</figcaption></figure>`).join('');
  await page.setViewportSize({ width: 4 * 270 + 5 * 12, height: 4 * (480 + 34) + 5 * 12 });
  await page.setContent(`<style>
    body{margin:0;background:#222;font:600 18px monospace;color:#eee}
    .g{display:grid;grid-template-columns:repeat(4,270px);gap:12px;padding:12px}
    figure{margin:0}.f{position:relative;width:270px;height:480px;overflow:hidden}
    img{width:270px;height:480px;display:block}
    i{position:absolute;background:rgba(255,0,60,.22);outline:1px dashed rgba(255,0,60,.8)}
    .t{left:0;right:0;top:0;height:62.5px}.b{left:0;right:0;bottom:0;height:95px}.r{top:0;bottom:0;right:0;width:30px}
    figcaption{height:30px;line-height:30px}</style><div class="g">${cells}</div>`);
  await page.waitForFunction(() => Array.from(document.images).every((im) => im.complete));
  await page.screenshot({ path: SHEET, fullPage: true });
  await browser.close();

  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(FRAMES, '%05d.png'),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(fps),
    '-movflags', '+faststart', OUT], { stdio: 'inherit' });
  if (!process.env.KEEP_FRAMES) fs.rmSync(FRAMES, { recursive: true, force: true });
  console.log('Selesai:', OUT, (fs.statSync(OUT).size / 1e6).toFixed(2) + ' MB');
})().catch((e) => { console.error(e); process.exit(1); });
