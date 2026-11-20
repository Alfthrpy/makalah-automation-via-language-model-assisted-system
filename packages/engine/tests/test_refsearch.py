import json
from collections import Counter

from malas.crews.models.TaskOutput import ReferenceItem
from malas.fulltext import fetch_fulltext, find_meta_pdf, resolve_pdf_url
from malas.refsearch import HttpClient, heuristic_plan, llm_plan, search_references
from malas.refsearch.models import Candidate, SectionQuery
from malas.refsearch.providers import (
    DOAJ,
    ArXiv,
    Crossref,
    EuropePMC,
    OpenAlex,
    _inverted_abstract,
    normalize_doi,
    providers_for,
)
from malas.refsearch.rank import choose, dedupe, is_valid, score


# --------------------------------------------------------------------------- session palsu
class Resp:
    def __init__(self, status=200, body="", headers=None):
        self.status_code, self.text, self.headers = status, body if isinstance(body, str) else json.dumps(body), headers or {}


class FakeSession:
    """routes: daftar (substring_url, handler). handler: Resp | list[Resp] (dipakai berurutan) | callable(params)->Resp | Exception."""

    def __init__(self, routes):
        self.routes, self.log = routes, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.log.append((url, params))
        for sub, h in self.routes:
            if sub in url:
                if isinstance(h, list):
                    h = h.pop(0) if len(h) > 1 else h[0]
                if callable(h):
                    h = h(params)
                if isinstance(h, Exception):
                    raise h
                return h
        return Resp(404)


def client(routes, **kw):
    sleeps = []
    c = HttpClient(session=FakeSession(routes), sleep=sleeps.append, **kw)
    c.sleeps = sleeps
    return c


# --------------------------------------------------------------------------- HttpClient
def test_retry_429_lalu_sukses_dan_hormati_retry_after():
    c = client([("x.org", [Resp(429, "", {"Retry-After": "2"}), Resp(200, {"ok": 1})])])
    assert c.get_json("https://x.org/a") == {"ok": 1}
    assert c.calls == 2 and any(s >= 2 for s in c.sleeps)


def test_timeout_semua_gagal_mengembalikan_none_tanpa_raise():
    c = client([("x.org", TimeoutError("boom"))], retries=2)
    assert c.get_json("https://x.org/a") is None


def test_circuit_breaker_dan_403_tidak_diulang():
    c = client([("x.org", Resp(403))])
    assert c.get_json("https://x.org/a") is None
    n = c.calls
    assert c.is_open("x.org") and c.get_json("https://x.org/b") is None and c.calls == n  # host dilewati

    c2 = client([("y.org", Resp(503))], retries=1, breaker_after=3)
    for _ in range(3):
        c2.get_json("https://y.org/a", {"q": _})
    assert c2.is_open("y.org")


def test_cache_disk_tidak_menyimpan_secret_di_kunci(tmp_path):
    routes = [("x.org", [Resp(200, {"v": 1}), Resp(200, {"v": 2})])]
    c = client(routes, cache_dir=tmp_path)
    assert c.get_json("https://x.org/a", {"q": "a", "api_key": "S1"}) == {"v": 1}
    assert c.get_json("https://x.org/a", {"q": "a", "api_key": "S2"}) == {"v": 1}  # kunci cache sama
    assert c.calls == 1 and c.cache_hits == 1
    c2 = client([("x.org", Resp(500))], cache_dir=tmp_path)  # proses baru, cache tetap ada
    assert c2.get_json("https://x.org/a", {"q": "a"}) == {"v": 1}


def test_jeda_per_host_dihormati():
    t = [0.0]
    sleeps = []
    c = HttpClient(session=FakeSession([("export.arxiv.org", Resp(200, "{}"))]),
                   sleep=lambda s: (sleeps.append(s), t.__setitem__(0, t[0] + s)), clock=lambda: t[0])
    c.get_text("https://export.arxiv.org/api/query", {"a": 1})
    c.get_text("https://export.arxiv.org/api/query", {"a": 2})
    assert sleeps and sleeps[0] >= 3.0


# --------------------------------------------------------------------------- provider (fixture respons)
OA = {"results": [
    {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1234/ABC.1", "title": "Deep Learning for Recommender Systems",
     "publication_year": 2022, "type": "article", "cited_by_count": 40, "language": "en",
     "authorships": [{"author": {"display_name": "Ada Lovelace"}}, {"author": {"display_name": "Alan Turing"}}],
     "primary_location": {"source": {"display_name": "Journal of AI"}, "landing_page_url": "https://j.org/1"},
     "best_oa_location": {"pdf_url": "https://oa.org/1.pdf"},
     "abstract_inverted_index": {"Recommender": [0], "systems": [1], "learn": [2], "preferences": [3]}},
    {"id": "https://openalex.org/W2", "doi": None, "title": "Erratum to something", "publication_year": 2022, "type": "erratum"},
]}


def test_openalex_parse_dan_params(monkeypatch):
    monkeypatch.setenv("MALAS_OPENALEX_API_KEY", "KEY")
    seen = {}
    c = client([("openalex.org", lambda p: (seen.update(p), Resp(200, OA))[1])], contact="a@b.c")
    out = OpenAlex().search(c, "recommender", "id", 5, 2015)
    assert len(out) == 1  # erratum dibuang
    r = out[0]
    assert r.doi == "10.1234/abc.1" and r.year == 2022 and r.oa_pdf_url == "https://oa.org/1.pdf"
    assert r.abstract == "Recommender systems learn preferences" and r.authors == ["Ada Lovelace", "Alan Turing"]
    assert "language:id" in seen["filter"] and seen["api_key"] == "KEY" and seen["mailto"] == "a@b.c"


def test_inverted_abstract():
    assert _inverted_abstract({"b": [1], "a": [0, 2]}) == "a b a"
    assert _inverted_abstract(None) is None


def test_crossref_parse():
    body = {"message": {"items": [{
        "DOI": "10.5555/XY", "title": ["Hukum Pidana <i>Baru</i> di Indonesia"], "issued": {"date-parts": [[2023, 5]]},
        "author": [{"given": "Budi", "family": "Santoso"}], "container-title": ["Jurnal Hukum"],
        "abstract": "<jats:p>Abstract Kajian hukum pidana.</jats:p>", "is-referenced-by-count": 3, "language": "id"},
        {"DOI": "10.1001/no-title", "title": []}]}}
    out = Crossref().search(client([("crossref", Resp(200, body))]), "hukum pidana", "id", 5, 2015)
    assert len(out) == 1 and out[0].title == "Hukum Pidana Baru di Indonesia" and out[0].authors == ["Budi Santoso"]
    assert out[0].abstract == "Kajian hukum pidana." and out[0].year == 2023 and out[0].url == "https://doi.org/10.5555/xy"


def test_europepmc_parse_nama_dibalik():
    body = {"resultList": {"result": [{
        "id": "123", "source": "MED", "doi": "10.9001/epmc", "title": "Stroke rehabilitation physiotherapy.",
        "authorString": "Smith JA, Lee K.", "pubYear": "2021", "journalTitle": "Phys Ther", "abstractText": "<h4>Background</h4>text",
        "citedByCount": 7, "fullTextUrlList": {"fullTextUrl": [{"documentStyle": "pdf", "availability": "Free", "url": "https://e.org/x.pdf"}]}}]}}
    out = EuropePMC().search(client([("europepmc", Resp(200, body))]), "stroke", "en", 5, 2015)
    assert out[0].authors == ["JA Smith", "K Lee"] or out[0].authors[0].split()[-1] == "Smith"
    assert out[0].oa_pdf_url == "https://e.org/x.pdf" and out[0].year == 2021


ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2301.00001v1</id><published>2023-01-02T00:00:00Z</published>
<title>Graph Neural Networks for Recommendation</title><summary> We study GNNs. </summary>
<author><name>Jane Roe</name></author></entry>
<entry><id>http://arxiv.org/abs/1001.00002v1</id><published>2010-01-02T00:00:00Z</published><title>Old paper about graph networks</title><summary>x</summary></entry></feed>"""


def test_arxiv_parse_dan_filter_tahun_dan_skip_indonesia():
    c = client([("arxiv.org", Resp(200, ATOM))])
    out = ArXiv().search(c, "graph neural recommendation", "en", 5, 2015)
    assert len(out) == 1 and out[0].oa_pdf_url == "https://arxiv.org/pdf/2301.00001v1" and out[0].authors == ["Jane Roe"]
    assert ArXiv().search(c, "graph neural recommendation", "id", 5, 2015) == []
    assert ArXiv().search(client([("arxiv.org", Resp(200, "<not xml"))]), "graph neural", "en", 5, 2015) == []


def test_doaj_parse():
    body = {"results": [{"id": "abc", "bibjson": {
        "title": "Pendidikan Karakter di Sekolah Dasar", "year": "2022", "author": [{"name": "Siti Aminah"}],
        "abstract": "Kajian pendidikan karakter.", "journal": {"title": "Jurnal Pendidikan", "language": ["ID"]},
        "identifier": [{"type": "doi", "id": "10.1001/doaj"}], "link": [{"type": "fulltext", "url": "https://j.id/a/1.pdf"}]}}]}
    out = DOAJ().search(client([("doaj.org", Resp(200, body))]), "pendidikan karakter", "id", 5, 2015)
    assert out[0].language == "id" and out[0].oa_pdf_url == "https://j.id/a/1.pdf" and out[0].doi == "10.1001/doaj"


def test_provider_respons_sampah_tidak_raise():
    for prov in (OpenAlex(), Crossref(), EuropePMC(), DOAJ()):
        for body in ("not json", "[]", '{"results": null}', "{}"):
            assert prov.search(client([("", Resp(200, body))]), "q", "en", 5, 2015) == []
        assert prov.search(client([("", Resp(500))], retries=1), "q", "en", 5, 2015) == []


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1234/ABC.1.") == "10.1234/abc.1"
    assert normalize_doi("tidak ada") is None


# --------------------------------------------------------------------------- rank
def cand(title, year=2022, doi=None, abstract="", src="openalex", ranks=(0,), cites=0, **kw):
    return Candidate(source=src, source_id=title, title=title, year=year, doi=doi, abstract=abstract or None,
                     ranks=list(ranks), cited_by=cites, **kw)


def test_dedupe_doi_judul_dan_merge():
    a = cand("Deep Learning for Recommender Systems", doi="10.1001/a", src="openalex", ranks=[0])
    b = cand("Deep learning for recommender systems.", doi=None, abstract="abstrak panjang di sini", src="crossref", ranks=[2],
             oa_pdf_url="https://x/1.pdf")
    c = cand("Hukum pidana baru", doi="10.1001/a", src="doaj")  # DOI sama dengan a, judul beda -> tetap duplikat
    out = dedupe([a, b, c])
    assert len(out) == 1
    m = out[0]
    assert m.abstract == "abstrak panjang di sini" and m.oa_pdf_url == "https://x/1.pdf"
    assert m.sources == {"openalex", "crossref", "doaj"} and sorted(m.ranks) == [0, 0, 2]


def test_validasi_tahun_judul_dan_klasik():
    assert not is_valid(cand("Dua kata", year=2022), 2015)
    assert not is_valid(cand("Judul yang cukup panjang", year=None), 2015)
    assert not is_valid(cand("Judul yang cukup panjang", year=2005), 2015)
    assert is_valid(cand("Judul yang cukup panjang", year=2005, cites=500), 2015)
    assert not is_valid(cand("Table of contents volume 3", year=2022), 2015)


def test_score_membuang_tidak_relevan_dan_mengurutkan():
    sq = SectionQuery("2.1 X", q_en="collaborative filtering recommender", q_id="sistem rekomendasi")
    rel = cand("Collaborative filtering recommender systems survey", abstract="matrix factorization recommender", ranks=[0], cites=50)
    sedikit = cand("Recommender interfaces and design", abstract="ui study", ranks=[3])
    ngawur = cand("Pertanian padi organik di lahan basah", abstract="padi", ranks=[1])
    ranked = score([sedikit, ngawur, rel], sq)
    assert ranked[0] is rel and ngawur not in ranked


def test_choose_batasi_pemakaian_ulang():
    cs = [cand(f"Paper nomor {i} tentang topik", doi=f"10.1001/{i}") for i in range(4)]
    used = Counter()
    for _ in range(3):
        picked = choose(cs, 2, used, max_reuse=2)
    assert {c.doi for c in picked} == {"10.1001/2", "10.1001/3"}  # dua pertama sudah terpakai 2x


# --------------------------------------------------------------------------- plan
def test_heuristic_plan_membuang_kata_generik():
    p = heuristic_plan("Akuntansi Syariah pada UMKM di Indonesia", ["1.1 Latar Belakang", "2.1 Konsep Zakat Perusahaan"])
    assert p[0].q_id == "Akuntansi Syariah pada UMKM di Indonesia" and "Zakat Perusahaan" in p[1].q_id
    assert p[0].indo is True and p[0].q_en == ""


def test_llm_plan_parse_dan_fallback():
    secs = ["2.1 Landasan Teori", "2.2 Analisis"]
    resp = 'Ini hasilnya: {"Landasan Teori": {"q_en": "sharia accounting", "q_id": "akuntansi syariah", "bidang": "ekonomi", "indo": true}, ' \
           '"2.2 Analisis": {"q_en": "xxx", "bidang": "ngawur"}}'
    p = llm_plan("Akuntansi Syariah", "Akuntansi", secs, lambda _: resp)
    assert p[0].q_en == "sharia accounting" and p[0].bidang == "ekonomi" and p[0].indo
    # JSON rusak -> semua dari heuristik
    p2 = llm_plan("Akuntansi Syariah", "Akuntansi", secs, lambda _: "bukan json")
    assert p2[0].q_id and p2[0].q_en == ""
    # LLM melempar error -> heuristik, tanpa raise
    def boom(_): raise RuntimeError("quota")
    assert len(llm_plan("Akuntansi Syariah", "Akuntansi", secs, boom)) == 2


def test_providers_for_bidang():
    assert providers_for("umum", False) == ["openalex", "crossref"]
    assert providers_for("medis", True) == ["openalex", "crossref", "europepmc", "doaj"]
    assert "arxiv" in providers_for("teknik", False)


# --------------------------------------------------------------------------- orkestrator
def _oa_page(n, year=2022):
    return {"results": [{"id": f"W{i}", "doi": f"https://doi.org/10.1001/t{i}", "title": f"Sistem rekomendasi berbasis kolaboratif varian {i}",
                         "publication_year": year, "type": "article", "cited_by_count": i, "authorships": [{"author": {"display_name": f"Pen {i}"}}],
                         "abstract_inverted_index": {"sistem": [0], "rekomendasi": [1], "kolaboratif": [2]}} for i in range(n)]}


def test_search_references_end_to_end_tanpa_llm():
    c = client([("openalex.org", Resp(200, _oa_page(6))), ("crossref.org", Resp(200, {"message": {"items": []}}))])
    plan = heuristic_plan("Sistem Rekomendasi Kolaboratif", ["1.1 Latar Belakang", "2.1 Landasan Teori", "2.2 Metode"])
    refs, rep = search_references(plan, "Sistem Rekomendasi Kolaboratif", c, k=2, year_min=2015)
    assert len(refs) >= 4 and not rep["sections_without_refs"]
    assert all(isinstance(r, ReferenceItem) and r.doi and r.sections and r.source == "openalex" for r in refs)
    assert rep["by_source"]["openalex"] == len(refs)
    pakai = Counter(s for r in refs for s in r.sections)
    assert all(v >= 2 for v in pakai.values())


def test_search_references_semua_provider_mati_tidak_raise():
    c = client([("", TimeoutError("down"))], retries=1)
    plan = heuristic_plan("Topik Apa Saja", ["2.1 Landasan Teori"])
    refs, rep = search_references(plan, "Topik Apa Saja", c)
    assert refs == [] and rep["sections_without_refs"] == ["2.1 Landasan Teori"]


def test_provider_meledak_tidak_menjatuhkan_orkestrator(monkeypatch):
    from malas.refsearch import orchestrator
    class Bad:
        def search(self, *a, **k): raise ValueError("bug provider")
    monkeypatch.setitem(orchestrator.PROVIDERS, "openalex", Bad())
    c = client([("crossref.org", Resp(200, {"message": {"items": [{"DOI": "10.1001/z", "title": ["Sistem rekomendasi kolaboratif terbaru"],
                "issued": {"date-parts": [[2022]]}, "author": [{"given": "A", "family": "B"}], "abstract": "sistem rekomendasi kolaboratif"}]}}))])
    refs, _ = search_references(heuristic_plan("Sistem Rekomendasi Kolaboratif", ["2.1 Teori"]), "Sistem Rekomendasi Kolaboratif", c, k=1, year_min=2015)
    assert len(refs) == 1 and refs[0].source == "crossref"


def test_referensi_lama_tanpa_field_baru_tetap_valid():
    r = ReferenceItem.model_validate({"title": "T", "authors": ["A B"], "year": 2020})
    assert r.sections == [] and r.doi is None


# --------------------------------------------------------------------------- full-text (OJS & OA)
def test_find_meta_pdf_ojs():
    page = '<head><meta name="citation_pdf_url" content="https://j.ac.id/index.php/x/article/view/12/34"></head>'
    assert find_meta_pdf(page) == "https://j.ac.id/index.php/x/article/download/12/34"
    assert find_meta_pdf('<meta content="https://a/b.pdf" name="citation_pdf_url">') == "https://a/b.pdf"
    assert find_meta_pdf("<html></html>") is None


def test_resolve_pdf_url_prioritas_dan_unpaywall():
    nope = lambda u: None
    assert resolve_pdf_url("https://doi.org/10.1001/x", nope, oa_pdf_url="https://oa/x.pdf") == ("pdf", "https://oa/x.pdf")
    up = lambda u: {"best_oa_location": {"url_for_pdf": "https://up/x.pdf"}} if "unpaywall" in u else None
    assert resolve_pdf_url("https://doi.org/10.1001/x", up, doi="10.1001/x", email="a@b.c") == ("pdf", "https://up/x.pdf")
    assert resolve_pdf_url("https://doi.org/10.1001/x", nope, doi="10.1001/x", landing=True) == ("landing", "https://doi.org/10.1001/x")


def test_fetch_fulltext_via_landing_ojs(tmp_path):
    from test_fulltext import _pdf
    pdf = _pdf("OJS full text " + "kolaborasi " * 80)
    page = '<meta name="citation_pdf_url" content="https://j.id/article/view/1/2">'

    class R:
        def __init__(self, content=b"", text="", ok=True): self.content, self.text, self.ok = content, text, ok
        def json(self): return {}

    def get(url, **kw):
        if "article/download/1/2" in url:
            return R(content=pdf)
        if "doi.org" in url or "semanticscholar" in url:
            return R(content=page.encode(), text=page) if "doi.org" in url else R(ok=False)
        return R(ok=False)

    ref = ReferenceItem(title="T", authors=["A B"], year=2022, link="https://doi.org/10.9001/ojs", doi="10.9001/ojs")
    text = fetch_fulltext(ref, tmp_path, get)
    assert text and "OJS full text" in text


def test_dedupe_tidak_menggabungkan_judul_beda_angka():
    a = cand("Pembelajaran fiqih waris dalam kurikulum merdeka bagian 1")
    b = cand("Pembelajaran fiqih waris dalam kurikulum merdeka bagian 2")
    assert len(dedupe([a, b])) == 2
