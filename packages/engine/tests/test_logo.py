import io
import zipfile

import pytest
from docx import Document
from malas import paths
from malas.docx_converter import DocxConverter
from malas.logo import CANVAS, MAX_INPUT_BYTES, LogoError, normalize_logo, placeholder_logo
from PIL import Image
from test_docx_converter import _makalah

TEMPLATE = str(paths.DEFAULT_TEMPLATE)


def _img(fmt="PNG", size=(200, 100), color=(200, 30, 30), mode="RGB"):
    b = io.BytesIO()
    Image.new(mode, size, color).save(b, format=fmt)
    return b.getvalue()


def _media(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        return z.read("word/media/image1.png")


def test_normalisasi_jadi_png_persegi_dan_gambar_utuh():
    out = Image.open(io.BytesIO(normalize_logo(_img(size=(300, 100)))))
    assert out.format == "PNG" and out.size == (CANVAS, CANVAS)
    # gambar lebar dimuat utuh di tengah (padding transparan di atas/bawah), tidak dipotong
    assert out.getpixel((CANVAS // 2, CANVAS // 2))[3] == 255 and out.getpixel((CANVAS // 2, 5))[3] == 0


def test_jpeg_diterima_dan_metadata_terbuang():
    b = io.BytesIO()
    im = Image.new("RGB", (120, 120), (10, 100, 200))
    exif = Image.Exif(); exif[0x010E] = "rahasia-lokasi"  # ImageDescription
    im.save(b, format="JPEG", exif=exif)
    out = normalize_logo(b.getvalue())
    assert b"rahasia-lokasi" not in out and Image.open(io.BytesIO(out)).format == "PNG"


@pytest.mark.parametrize("data,pesan", [
    (b"", "kosong"),
    (b"GIF89a" + b"0" * 50, "valid"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "valid"),
    (b"bukan gambar sama sekali", "valid"),
    (b"\x89PNG\r\n\x1a\n" + b"\0" * 20, "valid"),  # PNG terpotong
])
def test_input_buruk_ditolak(data, pesan):
    with pytest.raises(LogoError, match=pesan):
        normalize_logo(data)


def test_format_lain_dan_ukuran_ditolak():
    b = io.BytesIO(); Image.new("RGB", (50, 50)).save(b, format="GIF")
    with pytest.raises(LogoError, match="PNG atau JPEG"):
        normalize_logo(b.getvalue())
    with pytest.raises(LogoError, match="KB"):
        normalize_logo(b"x" * (MAX_INPUT_BYTES + 1))
    with pytest.raises(LogoError, match="Dimensi"):
        normalize_logo(_img(size=(8, 8)))


def test_decompression_bomb_ditolak():
    big = io.BytesIO(); Image.new("1", (20000, 20000)).save(big, format="PNG")  # ±puluhan KB, 400 juta piksel
    assert len(big.getvalue()) < MAX_INPUT_BYTES
    with pytest.raises(LogoError):
        normalize_logo(big.getvalue())


def test_convert_dengan_logo_kustom_menukar_gambar_sampul(tmp_path):
    logo = tmp_path / "logo.jpg"; logo.write_bytes(_img("JPEG", (180, 180), (0, 90, 160)))
    out = DocxConverter(TEMPLATE, str(tmp_path / "a.docx"), logo_path=str(logo)).convert(_makalah())
    got = Image.open(io.BytesIO(_media(out)))
    assert got.size == (CANVAS, CANVAS) and got.convert("RGB").getpixel((CANVAS // 2, CANVAS // 2))[2] > 120
    Document(out)  # dokumen tetap terbuka utuh


def test_tanpa_logo_netral_pakai_placeholder_dan_default_membiarkan_template(tmp_path):
    asli = _media(DocxConverter(TEMPLATE, str(tmp_path / "b.docx")).convert(_makalah()))
    netral = _media(DocxConverter(TEMPLATE, str(tmp_path / "c.docx"), neutral_logo=True).convert(_makalah()))
    assert netral == placeholder_logo() and asli != netral
    # default (CLI) tidak menyentuh gambar template
    with zipfile.ZipFile(TEMPLATE) as z:
        assert asli == z.read("word/media/image1.png")


def test_logo_rusak_membuat_konversi_gagal_jelas(tmp_path):
    bad = tmp_path / "x.png"; bad.write_bytes(b"bukan gambar")
    with pytest.raises(RuntimeError, match="PNG/JPEG"):
        DocxConverter(TEMPLATE, str(tmp_path / "d.docx"), logo_path=str(bad)).convert(_makalah())


def test_foto_jpeg_besar_dikecilkan_agar_hemat():
    import random
    rnd = random.Random(7)
    im = Image.new("RGB", (1200, 1200))
    px = im.load()
    for y in range(1200):
        for x in range(1200):
            px[x, y] = ((x * 255) // 1200 ^ rnd.randrange(0, 40), (y * 255) // 1200, rnd.randrange(0, 256) if (x // 6 + y // 6) % 2 else 80)
    b = io.BytesIO(); im.save(b, format="JPEG", quality=45)
    assert len(b.getvalue()) < MAX_INPUT_BYTES, len(b.getvalue())
    from malas.logo import MAX_OUTPUT_BYTES
    out = normalize_logo(b.getvalue())
    assert len(out) <= MAX_OUTPUT_BYTES and Image.open(io.BytesIO(out)).size == (CANVAS, CANVAS)
