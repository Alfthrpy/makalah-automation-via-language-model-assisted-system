// Prerender halaman publik setelah `vite build`: tulis dist/<rute>/index.html berisi meta, JSON-LD, dan konten statis
// (untuk crawler), plus dist/sitemap.xml dan dist/_redirects. React tetap mengambil alih saat aplikasi termuat.
// Node >= 22.18 mengimpor berkas .ts langsung (type stripping), jadi copy/teks hukum/panduan sama persis dengan situs.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { id } from "../src/copy/id.ts";
import { LEGAL_UPDATED, PRIVACY, TERMS } from "../src/features/legal/content.ts";
import { applyPage, buildPages, redirectsFile, sitemapXml } from "../src/seo/site.ts";
import guides from "../src/seo/guides.json" with { type: "json" };

const dist = fileURLToPath(new URL("../dist/", import.meta.url));
const template = await readFile(`${dist}index.html`, "utf8");
const pages = buildPages({ landing: id.landing, terms: TERMS, privacy: PRIVACY, legalUpdated: LEGAL_UPDATED, guides });

for (const p of pages) {
  const out = p.path === "/" ? `${dist}index.html` : `${dist}${p.path.slice(1)}/index.html`;
  if (p.path !== "/") await mkdir(out.replace(/\/index\.html$/, ""), { recursive: true });
  await writeFile(out, applyPage(template, p), "utf8");
}
await writeFile(`${dist}sitemap.xml`, sitemapXml(pages), "utf8");
await writeFile(`${dist}_redirects`, redirectsFile(pages), "utf8");
console.log(`prerender: ${pages.length} halaman (${pages.map((p) => p.path).join(", ")})`);
