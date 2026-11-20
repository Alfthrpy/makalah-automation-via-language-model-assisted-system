"""Logo kampus/sekolah untuk sampul makalah: validasi, normalisasi, placeholder netral, dan penukaran gambar di .docx.

Gambar dari pengguna TIDAK dipercaya: hanya PNG/JPEG, ukuran berkas dan piksel dibatasi, dibuka ulang dengan Pillow
dan dikodekan ulang sebagai PNG persegi (metadata/EXIF terbuang), sehingga yang masuk ke dokumen selalu PNG bersih.
"""
import io
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

MAX_INPUT_BYTES = 300_000  # berkas unggahan (klien biasanya sudah memperkecil)
MAX_PIXELS = 4000 * 4000  # batas anti "decompression bomb"
MAX_OUTPUT_BYTES = 350_000  # PNG hasil normalisasi (disimpan di DB per pengguna)
CANVAS = 600  # sisi kanvas persegi keluaran (px); di dokumen tampil ±6 cm
ALLOWED = {"PNG", "JPEG"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class LogoError(ValueError):
    """Gambar ditolak; pesan aman ditampilkan ke pengguna (Bahasa Indonesia)."""


def normalize_logo(data: bytes) -> bytes:
    """Validasi lalu kembalikan PNG persegi CANVASxCANVAS (latar transparan, gambar dimuat utuh di tengah)."""
    if not data:
        raise LogoError("Berkas logo kosong.")
    if len(data) > MAX_INPUT_BYTES:
        raise LogoError(f"Ukuran logo maksimal {MAX_INPUT_BYTES // 1000} KB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED:
                raise LogoError("Format logo harus PNG atau JPEG.")
            if probe.width * probe.height > MAX_PIXELS or min(probe.size) < 16:
                raise LogoError("Dimensi logo tidak wajar (terlalu besar atau terlalu kecil).")
            img = ImageOps.exif_transpose(probe)
            img.load()
    except LogoError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError, SyntaxError) as e:
        raise LogoError("Berkas bukan gambar PNG/JPEG yang valid.") from e
    img = img.convert("RGBA")
    img.thumbnail((CANVAS, CANVAS), Image.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (255, 255, 255, 0))
    canvas.paste(img, ((CANVAS - img.width) // 2, (CANVAS - img.height) // 2), img)
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)  # tanpa metadata
    if out.tell() > MAX_OUTPUT_BYTES:  # mis. foto JPEG besar: kurangi jadi 256 warna agar hemat
        out = io.BytesIO()
        canvas.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(out, format="PNG", optimize=True)
        if out.tell() > MAX_OUTPUT_BYTES:
            raise LogoError("Logo terlalu rumit. Pakai gambar yang lebih sederhana atau lebih kecil.")
    return out.getvalue()


def placeholder_logo() -> bytes:
    """Penanda netral 'LOGO' (lingkaran abu-abu), dipakai bila pengguna belum mengunggah logo."""
    size = CANVAS
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, size - 20, size - 20), outline=(150, 156, 172, 255), width=10, fill=(243, 244, 248, 255))
    try:
        font = ImageFont.load_default(size=96)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), "LOGO", font=font)
    d.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]), "LOGO",
           fill=(120, 126, 146, 255), font=font)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


_BLIP = re.compile(rb'<a:blip [^>]*r:embed="([^"]+)"')


def swap_cover_logo(docx_path: str | Path, png: bytes) -> bool:
    """Ganti gambar pertama di dokumen (logo sampul) dengan `png`. Mengembalikan False bila dokumen tak punya gambar.
    Hanya isi berkas media yang diganti; ukuran tampil di dokumen (extent) tetap, dan karena logo persegi, rasio terjaga."""
    path = Path(docx_path)
    with zipfile.ZipFile(path) as zin:
        doc_xml = zin.read("word/document.xml")
        m = _BLIP.search(doc_xml)
        if not m:
            return False
        rid = m.group(1).decode()
        rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
        t = re.search(rf'<Relationship [^>]*Id="{re.escape(rid)}"[^>]*Target="([^"]+)"', rels) \
            or re.search(rf'<Relationship [^>]*Target="([^"]+)"[^>]*Id="{re.escape(rid)}"', rels)
        if not t:
            return False
        target = "word/" + t.group(1).lstrip("/").removeprefix("word/")
        if not target.lower().endswith(".png"):
            return False  # hanya mengganti PNG dengan PNG agar tipe konten tetap valid
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    if target not in {i.filename for i, _ in items}:
        return False
    tmp = path.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            zout.writestr(info, png if info.filename == target else data)
    tmp.replace(path)
    return True


def apply_logo(docx_path: str | Path, logo_png: bytes | None, neutral: bool) -> None:
    """logo_png dipakai bila ada; bila tidak dan `neutral`, pakai placeholder; selain itu dokumen dibiarkan."""
    if logo_png is not None:
        swap_cover_logo(docx_path, logo_png)
    elif neutral:
        swap_cover_logo(docx_path, placeholder_logo())
