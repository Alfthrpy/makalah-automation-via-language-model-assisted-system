from malas.citations import (
    check_citations, citation_label, extract_citations, find_suspects, prune_unused_references,
)
from malas.crews.models.TaskOutput import Bab, ContentList, ContentText, Makalah, ReferenceItem, SubBab


def _refs():
    return [
        ReferenceItem(title="A", authors=["John Smith"], year=2024),
        ReferenceItem(title="B", authors=["Ana Lee", "Bob Kim"], year=2023),
        ReferenceItem(title="C", authors=["Eve Ray", "Tom Poe", "Al Fox"], year=2022),
        ReferenceItem(title="D (tidak dikutip)", authors=["Zed Zorn"], year=2021),
    ]


def test_extract_berbagai_format():
    teks = ("Menurut (Smith, 2024) dan (Lee & Kim, 2023; Ray dkk., 2022). "
            "Smith (2024) serta Lee dan Kim (2023) menambahkan. (Ray et al., 2022, hlm. 5)")
    got = {(c.surname, c.year) for c in extract_citations(teks)}
    assert got == {("smith", 2024), ("lee", 2023), ("ray", 2022)}


def test_extract_abaikan_tahun_biasa():
    assert extract_citations("Pada tahun 2024 (lihat tabel 3) terjadi kenaikan.") == []


def test_citation_label():
    r = _refs()
    assert citation_label(r[0]) == "(Smith, 2024)"
    assert citation_label(r[1]) == "(Lee & Kim, 2023)"
    assert citation_label(r[2]) == "(Ray dkk., 2022)"


def test_check_dan_prune():
    m = Makalah(daftar_pustaka=_refs(), bab={"II": Bab(subbab=[
        SubBab(judul="2.1", content=[ContentText(isi="Teori (Smith, 2024) dan (Palsu, 1999).")]),
        SubBab(judul="2.2", content=[ContentList(items=["butir (Lee & Kim, 2023)"])]),
    ])})
    rep = check_citations(m)
    assert rep.invalid == {"2.1": ["(Palsu, 1999)"]}
    assert rep.used_refs == {0, 1} and rep.unused_refs == [2, 3]
    assert prune_unused_references(m, rep) == 2
    assert [r.title for r in m.daftar_pustaka] == ["A", "B"]


def test_prune_aman_bila_tidak_ada_sitasi_cocok():
    m = Makalah(daftar_pustaka=_refs(), bab={"II": Bab(subbab=[SubBab(judul="2.1", content=[ContentText(isi="Tanpa sitasi.")])])})
    assert prune_unused_references(m, check_citations(m)) == 0
    assert len(m.daftar_pustaka) == 4


def _makalah_m_dkk():
    refs = [
        ReferenceItem(title="Gamification of teaching and learning", authors=["Raseena P M", "Maya C"], year=2026),
        ReferenceItem(title="B", authors=["Rizka Utami"], year=2024),
    ]
    teks = "Gamifikasi muncul (M dkk., 2026). Menurut M dkk. (2026) ada tiga perspektif; Utami (2024) setuju."
    return Makalah(daftar_pustaka=refs, bab={"II": Bab(subbab=[SubBab(judul="2.1", content=[ContentText(isi=teks)])])})


def test_label_nama_berinisial_di_belakang_tidak_jadi_satu_huruf():
    ref = ReferenceItem(title="X", authors=["Raseena P M", "Maya C"], year=2026)
    assert citation_label(ref) == "(Raseena & Maya, 2026)"


def test_label_yang_dihasilkan_selalu_lolos_verifier():
    refs = [ReferenceItem(title="X", authors=["Raseena P M", "Maya C", "Abdul Wasih K"], year=2026)]
    teks = f"Kalimat {citation_label(refs[0])} dan narasi Raseena dkk. (2026)."
    m = Makalah(daftar_pustaka=refs, bab={"II": Bab(subbab=[SubBab(judul="2.1", content=[ContentText(isi=teks)])])})
    rep = check_citations(m)
    assert rep.ok and rep.used_refs == {0} and rep.total_citations == 2


def test_sitasi_satu_huruf_dilaporkan_bukan_dibuang_diam_diam():
    """Regresi F01: '(M dkk., 2026)' dulu tak terdeteksi lalu referensinya terhapus senyap."""
    m = _makalah_m_dkk()
    rep = check_citations(m)
    assert rep.suspect == {"2.1": ["(M dkk., 2026)", "M dkk. (2026)"]}
    assert not rep.ok and rep.problems["2.1"] == ["(M dkk., 2026)", "M dkk. (2026)"]
    assert rep.used_refs == {1}  # hanya Utami yang terurai
    assert prune_unused_references(m, rep) == 0  # JANGAN memangkas bila ada suspect
    assert len(m.daftar_pustaka) == 2 and rep.pruned_titles == []


def test_prune_mencatat_judul_yang_dibuang():
    m = Makalah(daftar_pustaka=_refs(), bab={"II": Bab(subbab=[
        SubBab(judul="2.1", content=[ContentText(isi="Teori (Smith, 2024) dan (Lee & Kim, 2023).")])])})
    rep = check_citations(m)
    assert prune_unused_references(m, rep) == 2
    assert rep.pruned_titles == ["C", "D (tidak dikutip)"]


def test_find_suspects_tidak_menuduh_kurung_biasa():
    teks = "Lihat (Gambar 2, 2024), (Tabel 3, 2023), (lihat bab 2, 2024), dan (QS. Al-Baqarah, 2024) serta (Smith, 2024)."
    assert find_suspects(teks) == []
    assert find_suspects("Hasil (M dkk., 2026) dan (A, 2025).") == ["(M dkk., 2026)", "(A, 2025)"]
