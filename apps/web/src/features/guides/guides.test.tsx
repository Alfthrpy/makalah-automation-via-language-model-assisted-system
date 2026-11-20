import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import guidesRaw from "../../seo/guides.json";
import type { GuidesData } from "../../seo/site";
import GuidePage, { GuideIndex } from "./Guides";

const data = guidesRaw as GuidesData;

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/panduan" element={<GuideIndex />} />
        <Route path="/panduan/:slug" element={<GuidePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("halaman panduan", () => {
  it("indeks memuat semua artikel sebagai tautan dan mengatur judul + canonical", () => {
    at("/panduan");
    for (const g of data.guides) expect(screen.getByRole("link", { name: g.h1 })).toHaveAttribute("href", `/panduan/${g.slug}`);
    expect(document.title).toContain(data.index.title);
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://malas.alfthrpy.my.id/panduan");
  });
  it("artikel: h1, bagian, FAQ, judul dokumen, dan meta description", () => {
    const g = data.guides[0]!;
    at(`/panduan/${g.slug}`);
    expect(screen.getByRole("heading", { level: 1, name: g.h1 })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 2 }).length).toBeGreaterThanOrEqual(g.sections.length);
    expect(screen.getByText(g.faq[0]!.q)).toBeInTheDocument();
    expect(document.title).toBe(`${g.title} | MALAS`);
    expect(document.head.querySelector('meta[name="description"]')).toHaveAttribute("content", g.description);
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", expect.stringContaining("index,follow"));
  });
  it("slug tidak dikenal menampilkan 404 yang noindex", () => {
    at("/panduan/tidak-ada");
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex,follow");
  });
  it("meta dipulihkan saat halaman ditinggalkan", () => {
    document.title = "Awal";
    const { unmount } = at(`/panduan/${data.guides[0]!.slug}`);
    unmount();
    expect(document.title).toBe("Awal");
  });
});
