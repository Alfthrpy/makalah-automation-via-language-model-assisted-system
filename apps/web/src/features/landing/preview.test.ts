import { describe, expect, it } from "vitest";
import { buildPreview, topicParts } from "./preview";

describe("topicParts", () => {
  it("memecah judul di kata sambung dan membuang kata awalan topik", () => {
    expect(topicParts("Peran Kecerdasan Buatan dalam Pembelajaran Fiqih")).toEqual({
      a: "Peran Kecerdasan Buatan", b: "Pembelajaran Fiqih", conn: "dalam", core: "Kecerdasan Buatan",
    });
  });
  it("judul tanpa kata sambung dipakai utuh", () => {
    const p = topicParts("  Etika   Digital ");
    expect(p).toMatchObject({ a: "Etika Digital", b: "", conn: "", core: "Etika Digital" });
  });
});

describe("buildPreview", () => {
  it("memakai judul cadangan bila terlalu pendek", () => {
    expect(buildPreview("ab", "Judul Contoh Panjang").title).toBe("Judul Contoh Panjang");
  });
  it("menyusun 4 sub-bab dengan konteks b bila ada", () => {
    const p = buildPreview("Dampak Media Sosial terhadap Kesehatan Mental", "x");
    expect(p.subs).toHaveLength(4);
    expect(p.subs[1]).toBe("2.2 Gambaran Umum Kesehatan Mental");
    expect(p.subs[2]).toBe("2.3 Dampak Media Sosial terhadap Kesehatan Mental");
  });
});
