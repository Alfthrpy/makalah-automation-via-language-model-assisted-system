import { describe, expect, it } from "vitest";
import { LogoPrepError, fitContain, precheckLogo } from "./image";

describe("fitContain", () => {
  it("gambar lebar dimuat utuh dan dipusatkan", () => {
    expect(fitContain(1200, 600, 600)).toEqual({ w: 600, h: 300, x: 0, y: 150 });
  });
  it("gambar tinggi dimuat utuh dan dipusatkan", () => {
    expect(fitContain(300, 1200, 600)).toEqual({ w: 150, h: 600, x: 225, y: 0 });
  });
  it("gambar kecil tidak diperbesar", () => {
    expect(fitContain(100, 80, 600)).toEqual({ w: 100, h: 80, x: 250, y: 260 });
  });
  it("dimensi tidak valid ditolak", () => {
    expect(() => fitContain(0, 10, 600)).toThrow(LogoPrepError);
  });
});

describe("precheckLogo", () => {
  it("menerima PNG, JPEG, WebP", () => {
    for (const type of ["image/png", "image/jpeg", "image/webp"]) expect(() => precheckLogo({ type, size: 1000 })).not.toThrow();
  });
  it("menolak SVG, GIF, dan bukan-gambar (SVG bisa memuat skrip)", () => {
    for (const type of ["image/svg+xml", "image/gif", "text/html", "application/pdf", ""]) {
      expect(() => precheckLogo({ type, size: 1000 })).toThrow(/PNG atau JPEG/);
    }
  });
  it("menolak berkas sangat besar", () => {
    expect(() => precheckLogo({ type: "image/png", size: 13 * 1024 * 1024 })).toThrow(/12 MB/);
  });
});
