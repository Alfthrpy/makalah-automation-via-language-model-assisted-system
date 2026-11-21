import { describe, expect, it } from "vitest";
import { id } from "../copy/id";
import { LEGAL_UPDATED, PRIVACY, TERMS } from "../features/legal/content";
import guidesRaw from "./guides.json";
import {
  BRAND_FULL, LANDING_DESCRIPTION, LANDING_TITLE, LEGACY_HOST, LEGAL_LASTMOD, SITE_URL, applyPage, buildPages, esc, formatDateId, fullTitle, guideBody, headHtml,
  redirectsFile, sitemapXml, type GuidesData, type PageMeta,
} from "./site";

const guides = guidesRaw as GuidesData;
const TEMPLATE = `<head>\n<!--seo:start-->\n<title>x</title>\n<!--seo:end-->\n</head><body><div id="root"></div></body>`;

describe("headHtml / applyPage", () => {
  const p: PageMeta = { path: "/panduan/x", title: 'Judul "uji" <b>', description: "Deskripsi & lain", ogType: "article", jsonLd: [{ "@type": "Thing", name: "</script><script>alert(1)" }] };

  it("meng-escape atribut dan JSON-LD, serta memuat canonical + OG + Twitter", () => {
    const h = headHtml(p);
    expect(h).toContain("<title>Judul &quot;uji&quot; &lt;b&gt;</title>");
    expect(h).toContain('<link rel="canonical" href="https://malas.alfthrpy.my.id/panduan/x" />');
    expect(h).toContain('property="og:type" content="article"');
    expect(h).toContain('name="twitter:title"');
    expect(h).not.toContain("</script><script>"); // JSON-LD tidak bisa menutup skripnya sendiri
    expect(h).toContain("\\u003c/script>");
  });
  it("noindex menghasilkan meta robots noindex", () => {
    expect(headHtml({ ...p, noindex: true })).toContain('content="noindex,follow"');
    expect(headHtml(p)).toContain("index,follow");
  });
  it("applyPage mengganti blok SEO dan isi #root; templat tanpa penanda ditolak", () => {
    const out = applyPage(TEMPLATE, { ...p, bodyHtml: "<main>isi</main>" });
    expect(out).toContain('<div id="root"><main>isi</main></div>');
    expect(out).not.toContain("<title>x</title>");
    expect(() => applyPage("<head></head>", p)).toThrow(/penanda/);
    expect(() => applyPage("<!--seo:start--><!--seo:end-->", { ...p, bodyHtml: "z" })).toThrow(/root/);
  });
  it("isi dengan karakter khusus regex ($&) tidak merusak penggantian", () => {
    const out = applyPage(TEMPLATE, { ...p, bodyHtml: "<p>$& $1 $$</p>" });
    expect(out).toContain("<p>$& $1 $$</p>");
  });
});

describe("sitemap & redirects", () => {
  const pages: PageMeta[] = [
    { path: "/", title: "a", description: "a" },
    { path: "/panduan/x", title: "b", description: "b", lastmod: "2026-11-20" },
    { path: "/masuk", title: "c", description: "c", noindex: true },
  ];
  it("sitemap memuat halaman terindeks dengan lastmod dan membuang noindex", () => {
    const x = sitemapXml(pages);
    expect(x).toContain("<loc>https://malas.alfthrpy.my.id/</loc>");
    expect(x).toContain("<loc>https://malas.alfthrpy.my.id/panduan/x</loc><lastmod>2026-11-20</lastmod>");
    expect(x).not.toContain("/masuk");
  });
  it("_redirects melayani tiap halaman prerender persis di URL-nya", () => {
    const lines = redirectsFile(pages).trim().split("\n");
    expect(lines.slice(-2)).toEqual(["/panduan/x  /panduan/x/index.html  200", "/masuk  /masuk/index.html  200"]);
  });
  it("_redirects mengalihkan alamat lama (netlify.app) ke domain utama, paling atas dan dipaksa (301!)", () => {
    const lines = redirectsFile(pages).trim().split("\n");
    expect(lines[0]).toBe(`https://${LEGACY_HOST}/*  ${SITE_URL}/:splat  301!`);
    expect(lines[1]).toBe(`http://${LEGACY_HOST}/*  ${SITE_URL}/:splat  301!`);
    expect(SITE_URL).not.toContain(LEGACY_HOST);
    expect(lines.filter((l) => l.includes(LEGACY_HOST))).toHaveLength(2);
  });
});

describe("util", () => {
  it("formatDateId dan fullTitle", () => {
    expect(formatDateId("2026-11-20")).toBe("20 November 2026");
    expect(formatDateId("2026-01-05")).toBe("5 Januari 2026");
    expect(fullTitle("Cara cek DOI")).toBe("Cara cek DOI | MALAS");
    expect(fullTitle("MALAS: Penyusun Draf")).toBe("MALAS: Penyusun Draf");
    expect(esc(`<a href="x">&</a>`)).toBe("&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;");
  });
  it("LEGAL_LASTMOD selalu sejalan dengan LEGAL_UPDATED di teks hukum", () => {
    expect(formatDateId(LEGAL_LASTMOD)).toBe(LEGAL_UPDATED);
  });
  it("judul & deskripsi landing dalam batas wajar untuk hasil pencarian", () => {
    expect(LANDING_TITLE.length).toBeLessThanOrEqual(60);
    expect(LANDING_DESCRIPTION.length).toBeGreaterThanOrEqual(110);
    expect(LANDING_DESCRIPTION.length).toBeLessThanOrEqual(160);
  });
});

describe("buildPages (data nyata)", () => {
  const pages = buildPages({ landing: id.landing, terms: TERMS, privacy: PRIVACY, legalUpdated: LEGAL_UPDATED, guides });
  it("memuat landing, hukum, indeks panduan, dan tiap artikel dengan path unik", () => {
    const paths = pages.map((p) => p.path);
    expect(new Set(paths).size).toBe(paths.length);
    expect(paths).toEqual(expect.arrayContaining(["/", "/ketentuan", "/privasi", "/panduan"]));
    for (const g of guides.guides) expect(paths).toContain(`/panduan/${g.slug}`);
  });
  it("landing: WebApplication + FAQPage, dan FAQ terlihat di konten statis (syarat Google)", () => {
    const home = pages.find((p) => p.path === "/")!;
    const types = home.jsonLd!.map((j) => (j as { "@type": string })["@type"]);
    expect(types).toEqual(["WebApplication", "FAQPage"]);
    for (const f of id.landing.faq.items) expect(home.bodyHtml).toContain(esc(f.q));
    expect(home.bodyHtml).toContain("<h1>");
  });
  it("artikel: Article + BreadcrumbList (+ FAQPage) dan teks FAQ juga tampil di HTML statis", () => {
    for (const g of guides.guides) {
      const pg = pages.find((p) => p.path === `/panduan/${g.slug}`)!;
      const types = pg.jsonLd!.map((j) => (j as { "@type": string })["@type"]);
      expect(types.slice(0, 2)).toEqual(["Article", "BreadcrumbList"]);
      if (g.faq.length) { expect(types).toContain("FAQPage"); for (const f of g.faq) expect(pg.bodyHtml).toContain(esc(f.q)); }
      expect(pg.lastmod).toBe(g.updated);
    }
  });
  it("tiap halaman: judul, deskripsi, dan satu <h1> di konten statis", () => {
    for (const p of pages) {
      expect(p.title.length).toBeGreaterThan(10);
      expect(p.description.length).toBeGreaterThanOrEqual(60);
      expect((p.bodyHtml!.match(/<h1>/g) ?? []).length).toBe(1);
    }
  });
});

describe("guides.json (isi panduan)", () => {
  const slugs = guides.guides.map((g) => g.slug);
  const FORBIDDEN = /bebas plagiat|lolos deteksi|anti[- ]?plagiat|dijamin|pasti (?:dapat )?nilai|tanpa terdeteksi/i;
  const allText = (g: (typeof guides.guides)[number]) =>
    [g.title, g.h1, g.description, g.intro, ...g.sections.flatMap((s) => [s.h2, ...s.paragraphs, ...(s.bullets ?? []), ...(s.numbered ?? []), s.example ?? ""]),
      ...g.faq.flatMap((f) => [f.q, f.a])].join("\n");

  it("ada 5 artikel dengan slug unik dan berkas valid", () => {
    expect(guides.guides.length).toBeGreaterThanOrEqual(5);
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const g of guides.guides) {
      expect(g.slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
      expect(g.updated).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(g.sections.length).toBeGreaterThanOrEqual(4);
      expect(g.faq.length).toBeGreaterThanOrEqual(3);
      expect(g.related.length).toBeGreaterThanOrEqual(1);
      for (const r of g.related) expect(slugs).toContain(r);
      expect(g.related).not.toContain(g.slug);
    }
  });
  it("judul & deskripsi sesuai batas hasil pencarian", () => {
    for (const g of guides.guides) {
      expect(fullTitle(g.title).length, g.slug).toBeLessThanOrEqual(70);
      expect(g.description.length, g.slug).toBeGreaterThanOrEqual(110);
      expect(g.description.length, g.slug).toBeLessThanOrEqual(165);
    }
  });
  it("teks polos: tanpa markdown/HTML/emoji dan tanpa frasa terlarang (aturan kejujuran produk)", () => {
    for (const g of guides.guides) {
      const t = allText(g);
      expect(t, g.slug).not.toMatch(/\*\*|^#{1,6}\s|`|<\/?[a-z][^>]*>/m);
      expect(t, g.slug).not.toMatch(/\p{Extended_Pictographic}/u);
      expect(t, g.slug).not.toMatch(FORBIDDEN);
    }
  });
  it("guideBody memuat h1, FAQ, dan tautan 'Baca juga'", () => {
    const g = guides.guides[0]!;
    const html = guideBody(g, guides.guides);
    expect(html).toContain(`<h1>${esc(g.h1)}</h1>`);
    expect(html).toContain("Baca juga");
    expect(html).toContain(`/panduan/${g.related[0]}`);
  });
});

describe("berkas statis SEO", () => {
  it("index.html: satu meta description saja (di dalam blok seo)", async () => {
    const { readFileSync } = await import("node:fs");
    const html = readFileSync("index.html", "utf8");
    const start = html.indexOf("<!--seo:start-->");
    const end = html.indexOf("<!--seo:end-->");
    expect(html.match(/name="description"/g)?.length).toBe(1);
    expect(html.slice(0, start)).not.toContain('name="description"');
    expect(html.slice(start, end)).toContain('name="description"');
  });

  it("robots.txt tidak melarang halaman yang memakai noindex (crawler harus bisa membaca noindex)", async () => {
    const { readFileSync } = await import("node:fs");
    const robots = readFileSync("public/robots.txt", "utf8");
    expect(robots).not.toMatch(/Disallow:\s*\/(masuk|daftar)/);
  });
});

describe("merek: MALAS by studiocerdas", () => {
  it("teks merek di UI konsisten", () => {
    expect(id.brand.name).toBe("MALAS");
    expect(id.brand.by).toBe("by studiocerdas");
    expect(BRAND_FULL).toBe(`${id.brand.name} ${id.brand.by}`);
    expect(id.brand.homeLabel).toContain(BRAND_FULL);
    expect(id.brand.dashLabel).toContain(BRAND_FULL);
  });

  it("og:site_name, entitas JSON-LD, dan index.html memakai nama merek lengkap", () => {
    const pages = buildPages({ landing: id.landing, terms: TERMS, privacy: PRIVACY, legalUpdated: LEGAL_UPDATED, guides });
    const landing = pages.find((q) => q.path === "/")!;
    expect(headHtml(landing)).toContain(`<meta property="og:site_name" content="${BRAND_FULL}" />`);
    const app = (landing.jsonLd as Array<Record<string, any>>).find((j) => j["@type"] === "WebApplication")!;
    expect(app.name).toBe("MALAS"); // nama produk tetap MALAS; pembuatnya studiocerdas
    expect(app.author).toEqual({ "@type": "Organization", name: "studiocerdas" });
    const article = pages.find((q) => q.path.startsWith("/panduan/"))!;
    expect(JSON.stringify(article.jsonLd)).toContain(BRAND_FULL);
  });

  it("judul landing tetap berawalan MALAS (kesinambungan SEO)", () => {
    expect(LANDING_TITLE.startsWith("MALAS")).toBe(true);
  });
});
