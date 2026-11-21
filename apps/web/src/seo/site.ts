/** SEO: meta per halaman, JSON-LD, sitemap, dan HTML statis untuk prerender.
 *
 *  Murni (tanpa React/DOM) dan hanya memakai sintaks TypeScript yang bisa dihapus, sehingga DIPAKAI BERSAMA oleh:
 *  - aplikasi (useSeo.ts, halaman panduan), dan
 *  - skrip build `scripts/prerender.mjs` (Node mengimpor berkas .ts langsung).
 *  Ganti SITE_URL bila domain berubah (juga di public/robots.txt dan netlify.toml). */

export const SITE_URL = "https://malas.alfthrpy.my.id";
export const SITE_NAME = "MALAS";
export const BRAND_FULL = "MALAS by studiocerdas"; // nama merek lengkap (og:site_name, entitas JSON-LD)
const STUDIO_NAME = "studiocerdas";
export const OG_IMAGE = `${SITE_URL}/og.png`;
/** Tanggal ISO halaman Ketentuan/Privasi; samakan dengan LEGAL_UPDATED di features/legal/content.ts (dijaga tes). */
export const LEGAL_LASTMOD = "2026-11-20";

export interface GuideSection { h2: string; paragraphs: string[]; bullets?: string[]; numbered?: string[]; example?: string }
export interface Faq { q: string; a: string }
export interface Guide {
  slug: string; title: string; h1: string; description: string; updated: string; readingMinutes: number;
  intro: string; sections: GuideSection[]; faq: Faq[]; related: string[];
}
export interface GuidesData { index: { title: string; h1: string; description: string; intro: string }; guides: Guide[] }

export interface PageMeta {
  path: string;
  title: string; // isi <title> lengkap
  description: string;
  noindex?: boolean;
  ogType?: "website" | "article";
  lastmod?: string;
  jsonLd?: object[];
  bodyHtml?: string; // konten statis di dalam #root (diganti React saat aplikasi termuat)
}

type Block = string | string[];
interface LegalLike { title: string; intro: string; sections: { id: string; title: string; blocks: Block[] }[] }
interface LandingCopy {
  heroA: string; heroMark: string; heroB: string; lead: string;
  facts: { time: string; draft: string; key: string };
  steps: { title: string; items: { title: string; text: string }[] };
  honest: { title: string; items: { t: string; p: string }[] };
  faq: { title: string; items: Faq[] };
}

export const LANDING_TITLE = "MALAS: Penyusun Draf Makalah, Referensi Bisa Dicek";
export const LANDING_DESCRIPTION =
  "Susun draf makalah .docx dari judul: sitasi APA, daftar pustaka, referensi dari database jurnal yang bisa dicek. Mode uji gratis tanpa API key.";

export const TERMS_DESCRIPTION =
  "Aturan memakai MALAS, ringkas dan jelas: apa itu MALAS, tanggung jawabmu atas hasil draf, batas layanan, dan kuota.";
export const PRIVACY_DESCRIPTION =
  "Data apa yang dikirim dan disimpan MALAS, siapa yang menerimanya, berapa lama, dan cara menghapusnya. API key tidak disimpan secara bawaan.";

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
/** "2026-11-20" -> "20 November 2026" */
export function formatDateId(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${Number(m[3])} ${BULAN[Number(m[2]) - 1] ?? m[2]} ${m[1]}` : iso;
}

export function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function absUrl(path: string): string {
  return path === "/" ? `${SITE_URL}/` : `${SITE_URL}${path}`;
}

export function fullTitle(t: string): string {
  return t.includes(SITE_NAME) ? t : `${t} | ${SITE_NAME}`;
}

function ld(obj: object): string {
  return `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, "\\u003c")}</script>`;
}

/** Seluruh tag SEO/sosial untuk satu halaman (diletakkan di antara penanda <!--seo:start--> dan <!--seo:end-->). */
export function headHtml(p: PageMeta): string {
  const url = absUrl(p.path);
  const t = esc(p.title), d = esc(p.description);
  const tags = [
    `<title>${t}</title>`,
    `<meta name="description" content="${d}" />`,
    `<link rel="canonical" href="${url}" />`,
    p.noindex ? `<meta name="robots" content="noindex,follow" />` : `<meta name="robots" content="index,follow,max-image-preview:large" />`,
    `<meta property="og:type" content="${p.ogType ?? "website"}" />`,
    `<meta property="og:site_name" content="${BRAND_FULL}" />`,
    `<meta property="og:locale" content="id_ID" />`,
    `<meta property="og:title" content="${t}" />`,
    `<meta property="og:description" content="${d}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:image" content="${OG_IMAGE}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta property="og:image:alt" content="MALAS by studiocerdas: Kamu mager, MALAS yang gerak. Penyusun draf makalah." />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${t}" />`,
    `<meta name="twitter:description" content="${d}" />`,
    `<meta name="twitter:image" content="${OG_IMAGE}" />`,
    ...(p.jsonLd ?? []).map(ld),
  ];
  return tags.join("\n    ");
}

const SEO_BLOCK = /<!--seo:start-->[\s\S]*?<!--seo:end-->/;

/** Isi templat index.html (hasil build Vite) dengan meta dan konten statis halaman ini. */
export function applyPage(template: string, p: PageMeta): string {
  if (!SEO_BLOCK.test(template)) throw new Error("index.html tidak memuat penanda <!--seo:start-->…<!--seo:end-->");
  let html = template.replace(SEO_BLOCK, () => `<!--seo:start-->\n    ${headHtml(p)}\n    <!--seo:end-->`);
  if (p.bodyHtml) {
    if (!html.includes('<div id="root"></div>')) throw new Error('index.html tidak memuat <div id="root"></div>');
    html = html.replace('<div id="root"></div>', () => `<div id="root">${p.bodyHtml}</div>`);
  }
  return html;
}

export function sitemapXml(pages: PageMeta[]): string {
  const rows = pages
    .filter((p) => !p.noindex)
    .map((p) => `  <url><loc>${absUrl(p.path)}</loc>${p.lastmod ? `<lastmod>${p.lastmod}</lastmod>` : ""}</url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${rows.join("\n")}\n</urlset>\n`;
}

/** Netlify _redirects: tiap halaman prerender dilayani PERSIS di URL-nya (status 200, tanpa redirect). */
export function redirectsFile(pages: PageMeta[]): string {
  return [...legacyHostRedirects(), ...pages.filter((p) => p.path !== "/").map((p) => `${p.path}  ${p.path}/index.html  200`)].join("\n") + "\n";
}

/** Alamat lama (subdomain Netlify) yang dialihkan permanen ke SITE_URL. */
export const LEGACY_HOST = "malas-app.netlify.app";

/**
 * Aturan _redirects yang mengalihkan SEMUA permintaan ke alamat lama (http dan https, path dan query dipertahankan) ke
 * domain utama dengan 301. Harus berada PALING ATAS (urutan = prioritas) dan memakai `!` (force) supaya menang atas
 * rewrite halaman prerender. Bergantung pada tanda `from` berhost penuh, yang hanya cocok untuk host itu: deploy
 * preview/branch (`*--malas-app.netlify.app`) dan domain utama tidak terkena.
 */
export function legacyHostRedirects(): string[] {
  return ["https", "http"].map((s) => `${s}://${LEGACY_HOST}/*  ${SITE_URL}/:splat  301!`);
}

// --------------------------------------------------------------------------- HTML statis (untuk crawler)
function list(tag: "ul" | "ol", items: string[]): string {
  return `<${tag}>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</${tag}>`;
}

function faqHtml(title: string, faq: Faq[]): string {
  return `<section><h2>${esc(title)}</h2>${faq.map((f) => `<h3>${esc(f.q)}</h3><p>${esc(f.a)}</p>`).join("")}</section>`;
}

function wrap(inner: string): string {
  return `<main class="seo-static" id="main">${inner}</main>`;
}

export function landingBody(L: LandingCopy, guides: Guide[]): string {
  return wrap(
    `<h1>${esc(L.heroA + L.heroMark + L.heroB)}</h1><p>${esc(L.lead)}</p>` +
      list("ul", [L.facts.time, L.facts.draft, L.facts.key]) +
      `<p><a href="/daftar">Coba gratis</a> · <a href="/masuk">Masuk</a></p>` +
      `<section><h2>${esc(L.steps.title)}</h2>${list("ol", L.steps.items.map((s) => `${s.title}. ${s.text}`))}</section>` +
      `<section><h2>${esc(L.honest.title)}</h2>${list("ul", L.honest.items.map((h) => `${h.t}. ${h.p}`))}</section>` +
      faqHtml(L.faq.title, L.faq.items) +
      (guides.length
        ? `<section><h2>Panduan</h2><ul>${guides.map((g) => `<li><a href="/panduan/${g.slug}">${esc(g.h1)}</a></li>`).join("")}</ul></section>`
        : "") +
      `<p><a href="/ketentuan">Ketentuan Layanan</a> · <a href="/privasi">Kebijakan Privasi</a></p>`,
  );
}

export function legalBody(doc: LegalLike, updatedLabel: string): string {
  const blocks = (b: Block) => (Array.isArray(b) ? list("ul", b) : `<p>${esc(b)}</p>`);
  return wrap(
    `<h1>${esc(doc.title)}</h1><p>Terakhir diperbarui ${esc(updatedLabel)}</p><p>${esc(doc.intro)}</p>` +
      doc.sections.map((s) => `<section id="${esc(s.id)}"><h2>${esc(s.title)}</h2>${s.blocks.map(blocks).join("")}</section>`).join(""),
  );
}

function guideSections(g: Guide): string {
  return g.sections
    .map(
      (s) =>
        `<section><h2>${esc(s.h2)}</h2>${s.paragraphs.map((p) => `<p>${esc(p)}</p>`).join("")}` +
        (s.bullets ? list("ul", s.bullets) : "") + (s.numbered ? list("ol", s.numbered) : "") +
        (s.example ? `<pre>${esc(s.example)}</pre>` : "") + `</section>`,
    )
    .join("");
}

export function guideBody(g: Guide, all: Guide[]): string {
  const rel = g.related.map((s) => all.find((x) => x.slug === s)).filter((x): x is Guide => !!x);
  return wrap(
    `<nav aria-label="Jejak"><a href="/">Beranda</a> › <a href="/panduan">Panduan</a></nav>` +
      `<h1>${esc(g.h1)}</h1><p>Diperbarui ${esc(formatDateId(g.updated))} · ${g.readingMinutes} menit baca</p><p>${esc(g.intro)}</p>` +
      guideSections(g) + (g.faq.length ? faqHtml("Pertanyaan yang sering muncul", g.faq) : "") +
      (rel.length ? `<section><h2>Baca juga</h2><ul>${rel.map((r) => `<li><a href="/panduan/${r.slug}">${esc(r.h1)}</a></li>`).join("")}</ul></section>` : ""),
  );
}

export function guideIndexBody(data: GuidesData): string {
  return wrap(
    `<h1>${esc(data.index.h1)}</h1><p>${esc(data.index.intro)}</p>` +
      `<ul>${data.guides.map((g) => `<li><a href="/panduan/${g.slug}">${esc(g.h1)}</a> — ${esc(g.description)}</li>`).join("")}</ul>`,
  );
}

// --------------------------------------------------------------------------- daftar halaman + JSON-LD
export function buildPages(input: { landing: LandingCopy; terms: LegalLike; privacy: LegalLike; legalUpdated: string; guides: GuidesData }): PageMeta[] {
  const { landing, terms, privacy, legalUpdated, guides } = input;
  const org = { "@type": "Organization", name: BRAND_FULL, url: `${SITE_URL}/` };
  const faqLd = (faq: Faq[]) => ({
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: faq.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  });
  const pages: PageMeta[] = [
    {
      path: "/", title: LANDING_TITLE, description: LANDING_DESCRIPTION,
      jsonLd: [
        {
          "@context": "https://schema.org", "@type": "WebApplication", name: SITE_NAME, url: `${SITE_URL}/`, author: { "@type": "Organization", name: STUDIO_NAME },
          description: LANDING_DESCRIPTION, inLanguage: "id", applicationCategory: "EducationalApplication",
          operatingSystem: "Web", isAccessibleForFree: true,
        },
        faqLd(landing.faq.items),
      ],
      bodyHtml: landingBody(landing, guides.guides),
    },
    {
      path: "/ketentuan", title: fullTitle(terms.title), lastmod: LEGAL_LASTMOD,
      description: TERMS_DESCRIPTION,
      bodyHtml: legalBody(terms, legalUpdated),
    },
    {
      path: "/privasi", title: fullTitle(privacy.title), lastmod: LEGAL_LASTMOD,
      description: PRIVACY_DESCRIPTION,
      bodyHtml: legalBody(privacy, legalUpdated),
    },
  ];
  if (guides.guides.length) {
    pages.push({
      path: "/panduan", title: fullTitle(guides.index.title), description: guides.index.description,
      jsonLd: [{ "@context": "https://schema.org", "@type": "CollectionPage", name: guides.index.h1, url: absUrl("/panduan"), inLanguage: "id" }],
      bodyHtml: guideIndexBody(guides),
    });
  }
  for (const g of guides.guides) {
    const url = absUrl(`/panduan/${g.slug}`);
    pages.push({
      path: `/panduan/${g.slug}`, title: fullTitle(g.title), description: g.description, ogType: "article", lastmod: g.updated,
      jsonLd: [
        {
          "@context": "https://schema.org", "@type": "Article", headline: g.h1, description: g.description, inLanguage: "id",
          datePublished: g.updated, dateModified: g.updated, image: OG_IMAGE, mainEntityOfPage: url, author: org, publisher: org,
        },
        {
          "@context": "https://schema.org", "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Beranda", item: `${SITE_URL}/` },
            { "@type": "ListItem", position: 2, name: "Panduan", item: absUrl("/panduan") },
            { "@type": "ListItem", position: 3, name: g.h1, item: url },
          ],
        },
        ...(g.faq.length ? [faqLd(g.faq)] : []),
      ],
      bodyHtml: guideBody(g, guides.guides),
    });
  }
  return pages;
}
