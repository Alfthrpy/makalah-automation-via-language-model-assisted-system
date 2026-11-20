import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Legal from "../states/Legal";
import { CONTACT_URL, PRIVACY, TERMS } from "./content";

describe.each([["terms", TERMS], ["privacy", PRIVACY]] as const)("halaman hukum: %s", (doc, data) => {
  it("memuat judul, semua bagian, dan daftar isi yang menaut ke bagian yang ada", () => {
    const { container } = render(<Legal doc={doc} />);
    expect(screen.getByRole("heading", { level: 1, name: data.title })).toBeTruthy();
    for (const s of data.sections) {
      expect(screen.getByRole("heading", { level: 2, name: s.title })).toBeTruthy();
      expect(container.querySelector(`#${s.id}`)).not.toBeNull();
      const toc = within(screen.getByRole("navigation", { name: "Isi halaman" }));
      expect(toc.getByRole("link", { name: s.title }).getAttribute("href")).toBe(`#${s.id}`);
    }
  });
  it("id bagian unik dan tiap bagian berisi teks", () => {
    const ids = data.sections.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const s of data.sections) expect(s.blocks.length).toBeGreaterThan(0);
  });
  it("kontak berupa tautan nyata", () => {
    render(<Legal doc={doc} />);
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href") === CONTACT_URL);
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]?.getAttribute("rel")).toContain("noopener");
  });
});

describe("kesesuaian dengan perilaku sistem", () => {
  const flat = (d: typeof TERMS) => JSON.stringify(d);
  it("retensi 6 jam disebut di kedua dokumen", () => {
    expect(flat(TERMS)).toContain("6 jam");
    expect(flat(PRIVACY)).toContain("6 jam");
  });
  it("NIM tidak dikirim ke penyedia LLM, dan nama dosen/penyusun dikirim", () => {
    const sent = PRIVACY.sections.find((s) => s.id === "pihak-penerima")!;
    const text = JSON.stringify(sent);
    expect(text).toMatch(/nama dosen dan nama penyusun/);
    expect(text).toMatch(/NIM, kelas, universitas, fakultas, dan jurusan tidak dikirim/);
  });
  it("tidak ada klaim terlarang (lolos deteksi, jaminan nilai)", () => {
    for (const d of [TERMS, PRIVACY]) {
      const t = flat(d).toLowerCase();
      expect(t).not.toMatch(/dijamin lolos|pasti lolos|menjamin nilai|nilai (a|bagus)/);
    }
    expect(flat(TERMS)).toMatch(/tidak dirancang untuk menghindari pemeriksaan/);
  });
});
