import { describe, expect, it } from "vitest";
import { clerkAppearance } from "./auth";

// Regresi: tema terang di login tidak terbaca (teks putih di kartu putih) karena variabel memakai nama lama Clerk
// (colorText, colorInputText, ...) yang tidak dibaca lagi; warna teks lalu mengikuti mode gelap/terang OS.
describe("clerkAppearance", () => {
  const light = clerkAppearance("light").variables;
  const dark = clerkAppearance("dark").variables;

  it("mengisi variabel teks/input dengan nama yang dibaca Clerk", () => {
    for (const k of ["colorForeground", "colorMutedForeground", "colorInput", "colorInputForeground", "colorBackground", "colorNeutral", "colorBorder", "colorPrimaryForeground"] as const) {
      expect(light[k], k).toBeTruthy();
      expect(dark[k], k).toBeTruthy();
    }
  });

  it("tidak memakai nama lama yang diabaikan Clerk", () => {
    for (const k of ["colorText", "colorTextSecondary", "colorInputText", "colorInputBackground"]) {
      expect(k in light, k).toBe(false);
      expect(k in dark, k).toBe(false);
    }
  });

  it("teks berbeda dari latar pada tiap tema, dan terang vs gelap saling berlawanan", () => {
    expect(light.colorForeground).not.toBe(light.colorBackground);
    expect(dark.colorForeground).not.toBe(dark.colorBackground);
    expect(light.colorInputForeground).not.toBe(light.colorInput);
    expect(dark.colorInputForeground).not.toBe(dark.colorInput);
    expect(light.colorForeground).not.toBe(dark.colorForeground);
    expect(light.colorBackground).not.toBe(dark.colorBackground);
  });
});
