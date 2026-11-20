/** Persiapan logo di browser: foto HP bisa belasan MB, jadi diperkecil dan diubah ke PNG persegi sebelum diunggah.
 *  Server tetap memvalidasi ulang (PNG/JPEG, ≤300 KB) dan mengodekan ulang; ini hanya untuk kenyamanan dan hemat data. */

export const LOGO_MAX_BYTES = 300_000;
export const LOGO_BOX = 600;
const ACCEPT_RE = /^image\/(png|jpeg|webp)$/;
const MAX_SOURCE_BYTES = 12 * 1024 * 1024;

export class LogoPrepError extends Error {}

export const LOGO_ACCEPT = "image/png,image/jpeg,image/webp";

/** Skala gambar w×h agar muat utuh di kotak `box`×`box` (tanpa diperbesar) dan posisinya di tengah. */
export function fitContain(w: number, h: number, box: number): { w: number; h: number; x: number; y: number } {
  if (w <= 0 || h <= 0) throw new LogoPrepError("Gambar tidak valid.");
  const s = Math.min(1, box / w, box / h);
  const dw = Math.max(1, Math.round(w * s));
  const dh = Math.max(1, Math.round(h * s));
  return { w: dw, h: dh, x: Math.floor((box - dw) / 2), y: Math.floor((box - dh) / 2) };
}

/** Pemeriksaan sebelum decode (cepat, tanpa canvas). Melempar LogoPrepError berisi pesan untuk pengguna. */
export function precheckLogo(file: { type: string; size: number }): void {
  if (!ACCEPT_RE.test(file.type)) throw new LogoPrepError("Pilih gambar PNG atau JPEG.");
  if (file.size > MAX_SOURCE_BYTES) throw new LogoPrepError("Gambar terlalu besar (maksimal 12 MB).");
}

async function decode(file: Blob): Promise<{ src: CanvasImageSource; w: number; h: number; close: () => void }> {
  if (typeof createImageBitmap === "function") {
    const bmp = await createImageBitmap(file);
    return { src: bmp, w: bmp.width, h: bmp.height, close: () => bmp.close() };
  }
  const url = URL.createObjectURL(file);
  const img = new Image();
  await new Promise<void>((ok, bad) => { img.onload = () => ok(); img.onerror = () => bad(new Error("decode")); img.src = url; });
  return { src: img, w: img.naturalWidth, h: img.naturalHeight, close: () => URL.revokeObjectURL(url) };
}

function render(src: CanvasImageSource, w: number, h: number, box: number): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = box;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new LogoPrepError("Browser ini tidak bisa memproses gambar.");
  const f = fitContain(w, h, box);
  ctx.clearRect(0, 0, box, box);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, f.x, f.y, f.w, f.h);
  return new Promise((ok, bad) => canvas.toBlob((b) => (b ? ok(b) : bad(new LogoPrepError("Gagal memproses gambar."))), "image/png"));
}

/** Ubah berkas pilihan pengguna menjadi PNG persegi ≤ LOGO_MAX_BYTES (mencoba kotak lebih kecil bila perlu). */
export async function prepareLogo(file: File): Promise<Blob> {
  precheckLogo(file);
  let d;
  try { d = await decode(file); } catch { throw new LogoPrepError("Berkas bukan gambar yang valid."); }
  try {
    for (const box of [LOGO_BOX, 400, 300]) {
      const blob = await render(d.src, d.w, d.h, box);
      if (blob.size <= LOGO_MAX_BYTES) return blob;
    }
    throw new LogoPrepError("Logo terlalu rumit. Pakai gambar yang lebih sederhana atau lebih kecil.");
  } finally { d.close(); }
}
