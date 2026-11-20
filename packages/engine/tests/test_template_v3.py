"""Template v3 (S06): loop generik Bab I/III, daftar bernomor per sub-bab, tabel, TOC, tanda tangan, page-break."""
import importlib.util
import re
import zipfile
from pathlib import Path

import pytest
from docx import Document
from lxml import etree
from PIL import Image

from malas import docx_converter, paths
from malas.crews.models.TaskOutput import (
    Bab, ContentList, ContentTable, ContentText, Makalah, Penyusun, ReferenceItem, SubBab,
)
from malas.docx_converter import DocxConverter, infer_kind, normalize_for_template
from malas.template_check import (
    DAFTAR_NUM_ID, MODE_GENERIC, MODE_INDEXED, RULE_ID, V3_TEMPLATE_NAME, check_template, detect_template_mode,
)

V3 = paths.TEMPLATES_DIR / V3_TEMPLATE_NAME
OLD = paths.TEMPLATES_DIR / "template makalah.docx"
OLD2 = paths.TEMPLATES_DIR / "template makalah2.docx"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_template_v3.py"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def _tabel() -> ContentTable:
    return ContentTable(caption="Sintesis studi", header=["Penulis", "Desain", "Hasil"],
                        rows=[["A & B (2020)", "RCT", "naik <5%"], ["", " ", ""], ["C (2021)", "survei"]])


def _makalah() -> Makalah:
    return Makalah(
        judul="Riset & Pengembangan <AI>", mata_kuliah="MK", dosen_pengampu="Dosen",
        penyusun=[Penyusun(nama="Ani Rahma", nim="1"), Penyusun(nama="Budi Santoso", nim="2")], kelas="A",
        universitas="Universitas Contoh", fakultas="Fakultas Teknik", jurusan="Jurusan Informatika",
        kota="Bandung", tahun="2025", kata_pengantar="Paragraf pembuka.\n\nParagraf penutup kata pengantar.",
        bab={
            "I": Bab(judul="Pendahuluan", subbab=[
                SubBab(judul="1.1 Latar Belakang", content=[ContentText(isi="Isi LB p & q <b>.\nParagraf kedua.")]),
                SubBab(judul="1.2 Rumusan Masalah",
                       content=[ContentText(isi="Rumusannya sebagai berikut:\n1) RM satu?\n2) RM dua?\nPenjelasan.")]),
                SubBab(judul="1.3 Tujuan", content=[ContentList(items=["Tujuan satu", "Tujuan dua"])]),
                SubBab(judul="1.4 Manfaat", content=[ContentText(isi="1. Manfaat A\n2. Manfaat B\n3. Manfaat C")]),
                SubBab(judul="1.5 Metode Penulisan", content=[ContentText(isi="Kajian pustaka atas artikel.")]),
            ]),
            "II": Bab(judul="Pembahasan", subbab=[
                SubBab(judul="2.1 Konsep Dasar", content=[ContentText(isi="Isi konsep."), _tabel(),
                                                          ContentList(title_items="Poin:", items=["x", "y"])]),
                SubBab(judul="2.2 Tujuan Pembelajaran Bahasa", content=[ContentText(isi="Isi narasi 2.2.")]),
            ]),
            "III": Bab(judul="Penutup", subbab=[
                SubBab(judul="3.1 Kesimpulan", content=[ContentText(isi="Simpulan utama.")]),
                SubBab(judul="3.2 Saran", content=[ContentText(isi="- Saran satu\n- Saran dua")]),
            ]),
        },
        daftar_pustaka=[ReferenceItem(title="judul paper", authors=["John Smith"], year=2024, venue="Jurnal X")],
    )


def _render(tmp_path, template=V3, makalah=None, name="hasil.docx", **kw):
    conv = DocxConverter(str(template), str(tmp_path / name), **kw)
    out = conv.convert(makalah or _makalah())
    return conv, out


def _part(path, name="word/document.xml") -> bytes:
    with zipfile.ZipFile(path) as z:
        return z.read(name)


def _body(path):
    return etree.fromstring(_part(path)).find("w:body", NS)


def _ptext(p) -> str:
    return "".join(p.itertext())


def _num_id(p):
    v = p.xpath("./w:pPr/w:numPr/w:numId/@w:val", namespaces=NS)
    return v[0] if v else None


def _body_paras(path):
    return [el for el in _body(path) if etree.QName(el).localname == "p"]


def test_bab1_lima_bab3_dua_sub_bab_dan_judul_tidak_berganda(tmp_path):
    _, out = _render(tmp_path)
    teks = [_ptext(p).strip() for p in _body_paras(out)]
    for judul in ("Latar Belakang", "Rumusan Masalah", "Tujuan", "Manfaat", "Metode Penulisan",
                  "Konsep Dasar", "Kesimpulan", "Saran"):
        assert teks.count(judul) == 1, judul  # judul dari data, tanpa nomor (gaya Judul2 bernomor otomatis)
    gabung = "\n".join(teks)
    assert "1.1 Latar" not in gabung and "Bekalang" not in gabung
    assert "Isi LB p & q <b>." in teks and "Paragraf kedua." in teks
    assert "Kajian pustaka atas artikel." in teks and "Simpulan utama." in teks
    assert not any("{%" in t or "{{" in t for t in teks)  # semua tag Jinja tertangani
    assert "" not in teks[teks.index("Latar Belakang"):teks.index("Rumusan Masalah")]  # tanpa paragraf kosong sisa tag


def test_daftar_bernomor_mulai_ulang_per_sub_bab(tmp_path):
    _, out = _render(tmp_path)
    paras = _body_paras(out)
    teks = [_ptext(p).strip() for p in paras]
    grup = {}
    for p, t in zip(paras, teks):
        if t in {"RM satu?", "RM dua?", "Tujuan satu", "Tujuan dua", "Manfaat A", "Manfaat B", "Manfaat C",
                 "Saran satu", "Saran dua"}:
            grup.setdefault(t.split()[0], set()).add(_num_id(p))
    assert set(grup) == {"RM", "Tujuan", "Manfaat", "Saran"}
    assert all(len(ids) == 1 and None not in ids for ids in grup.values())  # satu numId per daftar
    ids = [next(iter(v)) for v in grup.values()]
    assert len(set(ids)) == 4  # numId berbeda -> penomoran tiap daftar mulai dari 1
    assert "Rumusannya sebagai berikut:" not in teks and "Penjelasan." not in teks  # S05: hanya butir
    numbering = _part(out, "word/numbering.xml").decode()
    abstract_rm = re.search(rf'<w:num w:numId="{DAFTAR_NUM_ID}"[^>]*><w:abstractNumId w:val="(\d+)"', numbering)[1]
    for i in ids:
        m = re.search(rf'<w:num w:numId="{i}"[^>]*>(.*?)</w:num>', numbering, re.S)
        assert m and f'<w:abstractNumId w:val="{abstract_rm}"/>' in m[1] and '<w:startOverride w:val="1"/>' in m[1]
    # Bab II tidak ditebak jadi daftar walau judulnya diawali "Tujuan"
    i22 = teks.index("Isi narasi 2.2.")
    assert _num_id(paras[i22]) is None


def test_tabel_terender_dengan_caption_dan_aman_xml(tmp_path):
    _, out = _render(tmp_path)
    xml = _part(out).decode()
    assert len(re.findall(r"<w:tbl[ >]", xml)) == 1  # <w:tbl ...> membawa deklarasi xmlns inline
    tbl = _body(out).find("w:tbl", NS)
    rows = tbl.findall("w:tr", NS)
    assert len(rows) == 3  # header + 2 baris; baris kosong dibuang
    assert all(len(r.findall("w:tc", NS)) == 3 for r in rows)  # baris pendek dipadatkan
    sel = ["".join(tc.itertext()) for r in rows for tc in r.findall("w:tc", NS)]
    assert sel[:3] == ["Penulis", "Desain", "Hasil"] and "A & B (2020)" in sel and "naik <5%" in sel
    assert rows[0].find("w:trPr/w:tblHeader", NS) is not None
    assert tbl.find("w:tblPr/w:tblBorders", NS) is not None
    teks = [p.text for p in Document(out).paragraphs]
    assert "Tabel 1. Sintesis studi" in teks
    assert teks.index("Isi konsep.") < teks.index("Tabel 1. Sintesis studi") < teks.index("Poin:")


def test_tabel_gagal_dirender_jadi_teks(tmp_path, monkeypatch):
    def rusak(*a, **k):
        raise RuntimeError("uji")

    monkeypatch.setattr(docx_converter, "build_table_subdoc", rusak)
    _, out = _render(tmp_path)
    teks = [p.text for p in Document(out).paragraphs]
    assert "<w:tbl>" not in _part(out).decode()
    assert "A & B (2020) | RCT | naik <5%" in teks and "Sintesis studi" in teks


def test_tabel_tanpa_isi_tidak_menggagalkan_render(tmp_path):
    m = _makalah()
    m.bab["II"].subbab[0].content = [ContentTable(caption="Kosong", header=[], rows=[["", ""]]),
                                     ContentText(isi="Sesudah tabel.")]
    _, out = _render(tmp_path, makalah=m)
    assert "Sesudah tabel." in [p.text for p in Document(out).paragraphs]


def test_field_toc_dan_update_fields(tmp_path):
    _, out = _render(tmp_path)
    instr = " ".join(t.text or "" for t in etree.fromstring(_part(out)).iter(f"{{{W}}}instrText"))
    assert 'TOC \\o "1-2" \\h \\z \\u' in instr
    assert b'<w:updateFields w:val="true"/>' in _part(out, "word/settings.xml")


def test_tanda_tangan_memuat_nama_penyusun_dan_keep_next(tmp_path):
    _, out = _render(tmp_path)
    paras = _body_paras(out)
    teks = [_ptext(p).strip() for p in paras]
    i_pen = teks.index("Penulis")
    i_di = teks.index("DAFTAR ISI")
    assert teks.index("Ani Rahma") > i_pen and teks.index("Budi Santoso") > teks.index("Ani Rahma")
    assert teks.index("Budi Santoso") < i_di
    assert teks[i_pen - 1].startswith("Bandung, ")
    i_akhir = teks.index("Paragraf penutup kata pengantar.")
    for p in paras[i_akhir:teks.index("Budi Santoso")]:
        assert p.find("w:pPr/w:keepNext", NS) is not None
    assert paras[teks.index("Paragraf pembuka.")].find("w:pPr/w:keepNext", NS) is None


def _page_break_before(paras, idx) -> bool:
    for prev in reversed(paras[:idx]):
        if prev.xpath(".//w:br[@w:type='page']", namespaces=NS) or prev.xpath("./w:pPr/w:sectPr", namespaces=NS):
            return True
        if _ptext(prev).strip():
            return False
    return False


def test_bab_iii_dan_bab_ii_diawali_page_break(tmp_path):
    _, out = _render(tmp_path)
    paras = _body_paras(out)
    teks = [_ptext(p).strip() for p in paras]
    for bab in ("BAB III", "BAB II", "BAB I"):
        idx = next(i for i, t in enumerate(teks) if t.startswith(bab))
        assert _page_break_before(paras, idx), bab
    kp = paras[teks.index("KATA PENGANTAR")]
    assert kp.find("w:pPr/w:pageBreakBefore", NS) is not None


def test_template_lama_tetap_merender_seperti_sebelumnya(tmp_path):
    from test_docx_converter import _makalah as makalah_lama

    m = makalah_lama()
    m.bab["II"].subbab[0].content.append(_tabel())
    conv, out = _render(tmp_path, template=OLD, makalah=m)
    assert conv.template_mode == MODE_INDEXED
    teks = "\n".join(p.text for p in Document(out).paragraphs)
    assert "Latar Bekalang" in teks  # judul harfiah template lama tetap (template lama tidak diubah)
    assert "Masalah satu" in teks and "Tujuan satu" in teks and "Simpulan satu" in teks
    assert "Penulis | Desain | Hasil" in teks and "A & B (2020) | RCT | naik <5%" in teks  # tabel -> teks
    assert "<w:tbl>" not in _part(out).decode()


def test_template2_lama_tetap_mode_indexed():
    assert detect_template_mode(OLD2) == MODE_INDEXED
    assert detect_template_mode(OLD) == MODE_INDEXED
    assert detect_template_mode(V3) == MODE_GENERIC


def test_check_template_v3_bersih_dan_lama_berisi_temuan():
    assert check_template(V3) == []
    lama = check_template(OLD)
    assert lama and {f.rule_id for f in lama} == {RULE_ID}
    pesan = " ".join(f.message for f in lama)
    for kata in ("TOC", "updateFields", "BAB III", "Bekalang", "nama penyusun", "Bab I", "Bab III"):
        assert kata in pesan, kata
    assert all(f.severity in {"blocker", "major"} for f in lama)


def test_check_template_berkas_rusak(tmp_path):
    p = tmp_path / "rusak.docx"
    p.write_bytes(b"bukan zip")
    hasil = check_template(p)
    assert len(hasil) == 1 and hasil[0].severity == "blocker"
    assert detect_template_mode(p) == MODE_INDEXED


def test_skrip_build_idempoten(tmp_path):
    spec = importlib.util.spec_from_file_location("build_template_v3", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a = mod.build(OLD, tmp_path / "a.docx")
    b = mod.build(OLD, tmp_path / "b.docx")
    with zipfile.ZipFile(a) as za, zipfile.ZipFile(b) as zb, zipfile.ZipFile(V3) as zv:
        assert za.namelist() == zb.namelist() == zv.namelist()
        for name in za.namelist():
            assert za.read(name) == zb.read(name) == zv.read(name), name  # berkas di repo = hasil skrip
    assert check_template(a) == []


def test_infer_kind():
    assert infer_kind("1.2 Rumusan Masalah") == "daftar"
    assert infer_kind("Tujuan Penulisan") == "daftar" and infer_kind("1.4 Manfaat") == "daftar"
    assert infer_kind("3.2 Saran") == "daftar"
    assert infer_kind("Latar Belakang") == "narasi" and infer_kind("Kesimpulan dan Saran") == "narasi"
    assert infer_kind("") == "narasi"


def test_normalize_generic_kind_dan_tabel_utuh():
    ctx = {"bab": {
        "I": {"subbab": [{"judul": "1.2 Rumusan Masalah", "content": [{"type": "text", "isi": "1) A\n2) B"}]}]},
        "II": {"subbab": [{"judul": "2.1 Tujuan X", "content": [{"type": "table", "header": ["a"], "rows": []}]}]},
    }}
    normalize_for_template(ctx, MODE_GENERIC)
    rm = ctx["bab"]["I"]["subbab"][0]
    assert rm["kind"] == "daftar" and rm["content"][0]["items"] == ["A", "B"]
    b2 = ctx["bab"]["II"]["subbab"][0]
    assert b2["kind"] == "narasi" and b2["content"][0]["type"] == "table"


def test_template_mode_tidak_dikenal_ditolak():
    with pytest.raises(ValueError):
        DocxConverter(str(V3), "x.docx", template_mode="lain")


def test_penyusun_dan_kata_pengantar_kosong_tetap_render(tmp_path):
    m = _makalah()
    m.penyusun = []
    m.kata_pengantar = ""
    m.bab["III"].subbab = []
    _, out = _render(tmp_path, makalah=m)
    teks = [p.text for p in Document(out).paragraphs]
    assert "Penulis" in teks and "Isi konsep." in teks


def test_logo_placeholder(tmp_path):
    conv, _ = _render(tmp_path, neutral_logo=True)
    assert conv.logo_placeholder is True
    logo = tmp_path / "logo.png"
    Image.new("RGB", (64, 64), (200, 30, 30)).save(logo)
    conv, _ = _render(tmp_path, name="b.docx", logo_path=str(logo))
    assert conv.logo_placeholder is False


@pytest.mark.parametrize("template", [V3, OLD])
def test_render_lolos_dibuka_python_docx(tmp_path, template):
    _, out = _render(tmp_path, template=template)
    doc = Document(out)
    assert doc.paragraphs and any("KATA PENGANTAR" in p.text for p in doc.paragraphs)
