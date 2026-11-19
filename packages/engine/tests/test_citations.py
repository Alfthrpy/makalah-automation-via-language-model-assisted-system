from malas.citations import (
    check_citations, citation_label, extract_citations, prune_unused_references,
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
