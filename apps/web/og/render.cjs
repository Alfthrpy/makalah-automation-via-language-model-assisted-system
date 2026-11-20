// Render gambar OG 1200x630: NODE_PATH=$(npm root -g) node apps/web/og/render.cjs
const { chromium } = require("playwright"); const path = require("path");
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
  await p.goto("file://" + path.join(__dirname, "og.html")); await p.evaluate(() => document.fonts.ready);
  const ok = await p.evaluate(() => document.fonts.check('800 20px "Bricolage"') && document.fonts.check('700 20px "Jakarta"'));
  if (!ok) throw new Error("font belum termuat");
  await p.screenshot({ path: path.join(__dirname, "..", "public", "og.png") }); await b.close(); console.log("og.png ditulis");
})();
