"""Tes pemformat APA 7 v2 (S03): golden, sentence case, urut alfabet, italik .docx, metadata provider."""
import json
import zipfile

from docx import Document
from malas import docx_converter, paths
from malas.apa import apa_sort_key, format_apa7, format_apa7_segments, protected_from, to_sentence_case
from malas.crews.models.TaskOutput import (
    Bab,
    ContentList,
    ContentText,
    Makalah,
    Penyusun,
    ReferenceItem,
    SubBab,
)
from malas.docx_converter import DocxConverter, italicize_ref_runs
from malas.refsearch.models import Candidate
from malas.refsearch.providers import Crossref, EuropePMC, OpenAlex, page_range
from malas.refsearch.rank import dedupe

UTAMI = {
    "title": "Gamifikasi dalam pembelajaran bahasa Arab di lembaga pendidikan Indonesia", "authors": ["Utami, R."],
    "year": 2024, "venue": "Nun: Journal of Arabic Studies", "volume": "4", "issue": "2", "pages": "36–52",
    "doi": "10.56633/nun.v4i2.1634", "link": "https://jurnal.example/nun/1634",
}
UTAMI_APA = ("Utami, R. (2024). Gamifikasi dalam pembelajaran bahasa Arab di lembaga pendidikan Indonesia. "
             "Nun: Journal of Arabic Studies, 4(2), 36–52. https://doi.org/10.56633/nun.v4i2.1634")
SHOLAHUDIN = {
    "title": ("PENGARUH GAMIFIKASI ASESMEN FORMATIF TERHADAP MOTIVASI BELAJAR SISWA DALAM PEMBELAJARAN BAHASA ARAB "
           "SEBAGAI BAHASA ASING"),
    "authors": ["Sholahudin, S.", "Syihabuddin, S."], "year": 2026,
    "venue": "JIPI (Jurnal Ilmiah Penelitian dan Pembelajaran Informatika)", "volume": "11", "issue": "2",
    "pages": "1711-1719", "doi": "10.29100/jipi.v11i2.7903",
}
SHOLAHUDIN_APA = (
    "Sholahudin, S., & Syihabuddin, S. (2026). Pengaruh gamifikasi asesmen formatif terhadap motivasi belajar siswa "
    "dalam pembelajaran bahasa Arab sebagai bahasa asing. JIPI (Jurnal Ilmiah Penelitian dan Pembelajaran "
    "Informatika), 11(2), 1711–1719. https://doi.org/10.29100/jipi.v11i2.7903"
)


# --------------------------------------------------------------------------- golden
def test_golden_utami_jurnal_lengkap():
    assert format_apa7(UTAMI) == UTAMI_APA
    assert format_apa7(ReferenceItem(**UTAMI).model_dump()) == UTAMI_APA
    segs = format_apa7_segments(UTAMI)
    assert "".join(t for t, _ in segs) == UTAMI_APA
    assert [t for t, it in segs if it] == ["Nun: Journal of Arabic Studies, 4"]  # jurnal + volume italik, issue tidak


def test_golden_sholahudin_judul_kapital():
    assert format_apa7(SHOLAHUDIN) == SHOLAHUDIN_APA


def test_tanpa_volume_venue_penulis():
    # tanpa penulis: judul di posisi penulis; tanpa jurnal: judul italik; tautan = link
    ref = {"title": "Laporan tahunan pendidikan", "authors": [], "year": 2023, "link": "https://a.b/c"}
    assert format_apa7(ref) == "Laporan tahunan pendidikan. (2023). https://a.b/c"
    assert format_apa7_segments(ref)[0] == ("Laporan tahunan pendidikan.", True)
    assert "tidak diketahui" not in format_apa7(ref)
    # venue saja (tanpa volume/halaman) -> render yang ada
    assert format_apa7({"title": "Judul", "authors": ["Ana Lee"], "year": 2021, "venue": "Jurnal X", "link": "u"}) \
        == "Lee, A. (2021). Judul. Jurnal X. u"
    # halaman tanpa volume, tahun kosong -> t.t.
    assert format_apa7({"title": "T", "authors": ["Ana Lee"], "year": 0, "venue": "J", "pages": "5-9"}) \
        == "Lee, A. (t.t.). T. J, 5–9."


def test_data_lama_given_family_tanpa_field_baru():
    ref = ReferenceItem(title="judul paper", authors=["John Smith", "Ana Lee", "Raseena P M"], year=2024,
                        link="https://x.y/1").model_dump()
    for k in ("volume", "issue", "pages"):
        ref.pop(k)
    assert format_apa7(ref) == "Smith, J., Lee, A., & Raseena, P. M. (2024). Judul paper. https://x.y/1"


# --------------------------------------------------------------------------- sentence case
def test_sentence_case_kapital_dan_akronim():
    t = ("PENGEMBANGAN KURIKULUM PENDIDIKAN AGAMA ISLAM (PAI) SECARA KONTEKSTUAL DAN ADAPTIF TERHADAP "
         "PERKEMBANGAN TEKNOLOGI DIGITAL")
    assert to_sentence_case(t, set()) == ("Pengembangan kurikulum pendidikan agama Islam (PAI) secara kontekstual "
                                          "dan adaptif terhadap perkembangan teknologi digital")


def test_sentence_case_title_case_titik_dua_dan_kapital_tengah():
    t = "The Effect Of Gamification On Arabic Learning: A Meta-Analysis Of iPhone Apps In SMP"
    assert to_sentence_case(t, set()) == "The effect of gamification on Arabic learning: A meta-analysis of iPhone apps in SMP"


def test_sentence_case_tidak_merusak_judul_benar_dan_nama_diri_dari_data():
    benar = "Gamifikasi dalam pembelajaran bahasa Arab di lembaga pendidikan Indonesia"
    assert to_sentence_case(benar, set()) == benar
    assert to_sentence_case("Pengaruh Media Al-Qur'an Digital Terhadap Hafalan Santri", set()) \
        == "Pengaruh media Al-Qur'an digital terhadap hafalan santri"
    ref = {"title": "STRATEGI DAKWAH MUHAMMADIYAH DI KOTA YOGYAKARTA", "authors": [], "year": 2022,
           "excerpt": "Penelitian ini mengkaji dakwah Muhammadiyah di Yogyakarta. Dakwah Muhammadiyah berkembang."}
    assert protected_from(ref) >= {"Muhammadiyah", "Yogyakarta"}
    assert format_apa7(ref).startswith("Strategi dakwah Muhammadiyah di kota Yogyakarta. (2022).")
    # venue Title-Case tidak menjadi sinyal (kata "Pembelajaran" tetap kecil), hanya akronim "JIPI"
    assert protected_from({"venue": SHOLAHUDIN["venue"]}) == {"JIPI"}


def test_sentence_case_bisa_dimatikan(monkeypatch):
    monkeypatch.setenv("MALAS_APA_SENTENCECASE", "0")
    assert format_apa7(SHOLAHUDIN).startswith("Sholahudin, S., & Syihabuddin, S. (2026). PENGARUH GAMIFIKASI")


# --------------------------------------------------------------------------- urut alfabet
def test_urut_alfabet_kunci():
    refs = [
        {"title": "Zeta", "authors": ["Ábel Zainal"], "year": 2020},
        {"title": "beta", "authors": ["Budi Santoso"], "year": 2021},
        {"title": "Alfa", "authors": ["Budi Santoso"], "year": 2019},
        {"title": "Mandiri", "authors": [], "year": 2020},
        {"title": "x", "authors": ["Ana Ábidin"], "year": 2020},
    ]
    urut = [r["title"] for r in sorted(refs, key=apa_sort_key)]
    assert urut == ["x", "Mandiri", "Alfa", "beta", "Zeta"]


def _makalah(refs):
    return Makalah(
        judul="Judul Uji", mata_kuliah="MK", dosen_pengampu="Dosen", penyusun=[Penyusun(nama="A", nim="1")],
        kelas="A", universitas="Universitas Contoh", fakultas="Fakultas Teknik", jurusan="Jurusan Informatika",
        kota="Bandung", tahun="2025",
        bab={
            "I": Bab(judul="Pendahuluan", subbab=[
                SubBab(judul="1.1 Latar Belakang", content=[ContentText(isi="Isi latar belakang")]),
                SubBab(judul="1.2 Rumusan Masalah", content=[ContentText(isi="1. Masalah satu")]),
                SubBab(judul="1.3 Tujuan", content=[ContentList(items=["Tujuan satu"])]),
            ]),
            "II": Bab(judul="Pembahasan", subbab=[SubBab(judul="2.1 Teori", content=[ContentText(isi="Isi")])]),
            "III": Bab(judul="Penutup", subbab=[SubBab(judul="3.1 Kesimpulan", content=[ContentText(isi="S")])]),
        },
        daftar_pustaka=refs,
    )


def test_context_urut_alfabet_tanpa_mengubah_state():
    refs = [ReferenceItem(**UTAMI), ReferenceItem(**SHOLAHUDIN),
            ReferenceItem(title="Kajian awal", authors=["Ahmad Fauzi"], year=2020, link="u")]
    m = _makalah(refs)
    ctx = DocxConverter(str(paths.DEFAULT_TEMPLATE))._generate_context(m)
    assert [s.split(",")[0] for s in ctx["daftar_pustaka_formatted"]] == ["Fauzi", "Sholahudin", "Utami"]
    assert [r.title for r in m.daftar_pustaka] == [r.title for r in refs]  # state tidak diurutkan
    assert ctx["daftar_pustaka_segmen"][ctx["daftar_pustaka_formatted"][2]][1] == ["Nun: Journal of Arabic Studies, 4",
                                                                                   True]


# --------------------------------------------------------------------------- italik .docx
def _runs_italik(path):
    doc = Document(path)
    out = {}
    for p in doc.paragraphs:
        for r in p.runs:
            out[r.text] = bool(r.italic)
    return out


def test_render_docx_italik_nama_jurnal(tmp_path):
    out = DocxConverter(str(paths.DEFAULT_TEMPLATE), str(tmp_path / "a.docx")).convert(
        _makalah([ReferenceItem(**UTAMI), ReferenceItem(title="Buku <A&B>", authors=["Ana Lee"], year=2020)]))
    teks = "\n".join(p.text for p in Document(out).paragraphs)
    assert UTAMI_APA in teks and "Lee, A. (2020). Buku <A&B>." in teks
    runs = _runs_italik(out)
    assert runs["Nun: Journal of Arabic Studies, 4"] is True
    assert runs["(2), 36–52. https://doi.org/10.56633/nun.v4i2.1634"] is False
    assert runs["Buku <A&B>."] is True  # tanpa jurnal: judul italik
    xml = zipfile.ZipFile(out).read("word/document.xml").decode()
    i = xml.index("Nun: Journal of Arabic Studies, 4")
    run = xml[xml.rindex("<w:r>", 0, i):i]
    assert "<w:i/>" in run and "Times New Roman" in run  # format run template dipertahankan


def test_italicize_ref_runs_tanpa_pola_dibiarkan():
    xml = "<w:p><w:r><w:t>{{judul}}</w:t></w:r></w:p>"
    assert italicize_ref_runs(xml) == xml
    xml2 = '<w:r><w:rPr><w:rFonts w:ascii="X"/><w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">{{ref}}</w:t></w:r>'
    out = italicize_ref_runs(xml2)
    assert '<w:rFonts w:ascii="X"/><w:i/><w:iCs/><w:sz w:val="24"/>' in out and "{% for seg in" in out


def test_richtext_gagal_kembali_ke_teks_polos(tmp_path, monkeypatch):
    def boom(xml):
        raise RuntimeError("pola rusak")

    monkeypatch.setattr(docx_converter, "italicize_ref_runs", boom)
    out = DocxConverter(str(paths.DEFAULT_TEMPLATE), str(tmp_path / "b.docx")).convert(_makalah([ReferenceItem(**UTAMI)]))
    assert UTAMI_APA in "\n".join(p.text for p in Document(out).paragraphs)

    # render ber-italik meledak di tengah jalan -> render ulang teks polos dengan DocxTemplate biasa
    monkeypatch.setattr(docx_converter._ApaDocxTemplate, "render", lambda *a, **k: (_ for _ in ()).throw(ValueError()))
    out = DocxConverter(str(paths.DEFAULT_TEMPLATE), str(tmp_path / "c.docx")).convert(_makalah([ReferenceItem(**UTAMI)]))
    runs = _runs_italik(out)
    assert runs.get(UTAMI_APA) is False


# --------------------------------------------------------------------------- metadata provider
class _Http:
    contact = None

    def __init__(self, body):
        self.body, self.params = body, None

    def get_json(self, url, params=None):
        self.params = params
        return json.loads(json.dumps(self.body))


def test_page_range():
    assert page_range("36", "52") == "36–52"
    assert page_range("36", "36") == "36" and page_range("e123", None) == "e123"
    assert page_range("36-52") == "36–52" and page_range(None, None) is None


def test_openalex_biblio():
    body = {"results": [{"id": "W1", "doi": "https://doi.org/10.56633/NUN.V4I2.1634", "title": UTAMI["title"],
                         "publication_year": 2024, "authorships": [{"author": {"display_name": "Rizka Utami"}}],
                         "primary_location": {"source": {"display_name": UTAMI["venue"]}},
                         "biblio": {"volume": "4", "issue": "2", "first_page": "36", "last_page": "52"}}]}
    http = _Http(body)
    c = OpenAlex().search(http, "q", "en", 5, 2015)[0]
    assert "biblio" in http.params["select"]
    assert (c.volume, c.issue, c.pages) == ("4", "2", "36–52")
    no_bib = OpenAlex().search(_Http({"results": [dict(body["results"][0], biblio=None)]}), "q", "en", 5, 2015)[0]
    assert (no_bib.volume, no_bib.issue, no_bib.pages) == (None, None, None)


def test_crossref_dan_europepmc_volume_halaman():
    cr = {"message": {"items": [{"DOI": "10.1/x", "title": ["T"], "volume": "11", "issue": "2", "page": "1711-1719"}]}}
    http = _Http(cr)
    c = Crossref().search(http, "q", "en", 5, 2015)[0]
    assert "volume,issue,page" in http.params["select"] and (c.volume, c.issue, c.pages) == ("11", "2", "1711–1719")
    ep = {"resultList": {"result": [{"id": "1", "title": "T", "journalVolume": "7", "issue": "3", "pageInfo": "e10"}]}}
    e = EuropePMC().search(_Http(ep), "q", "en", 5, 2015)[0]
    assert (e.volume, e.issue, e.pages) == ("7", "3", "e10")


def test_merge_mengisi_field_bibliografis_kosong():
    a = Candidate(source="openalex", source_id="a", title="Judul Sama Persis", doi="10.1/a", ranks=[0])
    b = Candidate(source="crossref", source_id="b", title="Judul sama persis", doi="10.1/a", ranks=[1],
                  volume="4", issue="2", pages="36–52")
    m = dedupe([a, b])[0]
    assert (m.volume, m.issue, m.pages) == ("4", "2", "36–52")
