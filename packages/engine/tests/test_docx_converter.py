from pathlib import Path

from docx import Document

from malas.crews.models.TaskOutput import (
    Bab, ContentList, ContentText, Makalah, Penyusun, ReferenceItem, SubBab,
)
from malas import paths
from malas.docx_converter import DocxConverter, format_apa7

TEMPLATE = paths.DEFAULT_TEMPLATE


def _makalah() -> Makalah:
    # Sengaja "salah bentuk": Rumusan Masalah berupa teks (bukan list),
    # Kesimpulan berupa list (bukan teks) -> harus dinormalisasi converter.
    return Makalah(
        judul="Judul Uji", mata_kuliah="MK", dosen_pengampu="Dosen",
        penyusun=[Penyusun(nama="A", nim="1")], kelas="A",
        universitas="Universitas Contoh", fakultas="Fakultas Teknik",
        jurusan="Jurusan Informatika", kota="Bandung", tahun="2025",
        bab={
            "I": Bab(judul="Pendahuluan", subbab=[
                SubBab(judul="1.1 Latar Belakang", content=[ContentText(isi="Isi latar belakang")]),
                SubBab(judul="1.2 Rumusan Masalah", content=[ContentText(isi="1. Masalah satu\n2. Masalah dua")]),
                SubBab(judul="1.3 Tujuan", content=[ContentList(items=["Tujuan satu"])]),
            ]),
            "II": Bab(judul="Pembahasan", subbab=[
                SubBab(judul="2.1 Teori", content=[ContentText(isi="Isi teori")]),
            ]),
            "III": Bab(judul="Penutup", subbab=[
                SubBab(judul="3.1 Kesimpulan", content=[ContentList(items=["Simpulan satu"])]),
            ]),
        },
        daftar_pustaka=[ReferenceItem(title="judul paper", authors=["John Smith"], year=2024, link=None)],
    )


def test_convert_menormalisasi_bentuk_konten(tmp_path):
    out = DocxConverter(str(TEMPLATE), str(tmp_path / "hasil.docx")).convert(_makalah())
    teks = "\n".join(p.text for p in Document(out).paragraphs)

    assert "Isi latar belakang" in teks
    assert "Masalah satu" in teks and "Masalah dua" in teks
    assert "Simpulan satu" in teks
    assert "UNIVERSITAS Contoh" in teks  # tidak dobel "UNIVERSITAS Universitas"
    assert "FAKULTAS Teknik" in teks


def test_format_apa7_tanpa_titik_ganda_dan_tanpa_none():
    ref = format_apa7({"authors": ["Jane"], "year": 2020, "title": "judul", "link": None})
    assert ".." not in ref and "None" not in ref
    assert format_apa7({"authors": ["John Smith"], "year": 2024, "title": "x", "link": "u"}).startswith("Smith, J. (2024).")


def test_karakter_khusus_xml_tidak_hilang(tmp_path):
    m = _makalah()
    m.judul = "Riset & Pengembangan <AI>"
    m.daftar_pustaka = [ReferenceItem(title="x", authors=["Ana Lee", "Bob Kim"], year=2024, link="https://a.b/?x=1&y=2")]
    m.bab["I"].subbab[0].content = [ContentText(isi="p & q <b>")]
    out = DocxConverter(str(TEMPLATE), str(tmp_path / "esc.docx")).convert(m)
    teks = "\n".join(p.text for p in Document(out).paragraphs)

    assert "Riset & Pengembangan <AI>" in teks
    assert "p & q <b>" in teks
    assert "Lee, A. & Kim, B." in teks
    assert "?x=1&y=2" in teks
