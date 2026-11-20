from types import SimpleNamespace

from malas.crews.models.TaskOutput import ReferenceItem
from malas.fulltext import (
    FullTextStore, bm25_rank, chunk_text, extract_pdf_text, fetch_fulltext, resolve_pdf_url,
)

_DASAR = (
    "Collaborative filtering predicts user preferences from the ratings of similar users. "
    "Matrix factorization learns latent factors for users and items from sparse rating data. "
    "The cold start problem occurs when a new user has no ratings available for the system. "
    "Hybrid recommender systems combine content features with collaborative signals to reduce sparsity. "
    "Evaluation uses precision recall and root mean squared error on held out test sets. "
    "Deep learning models such as autoencoders capture nonlinear interactions between users and items. "
)
# tiap pengulangan diberi penanda unik agar chunk tidak identik
ISI = " ".join(_DASAR + f"Section {i} ends here." for i in range(6)) + " References [1] A. Author. Some paper. 2010. " * 5


def _pdf(text: str) -> bytes:
    """PDF 1 halaman minimal berisi satu baris teks (xref dihitung benar)."""
    stream = f"BT /F1 10 Tf 20 700 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def test_resolve_url():
    nope = lambda u: None
    assert resolve_pdf_url("http://arxiv.org/abs/2301.01234v2", nope) == ("pdf", "https://arxiv.org/pdf/2301.01234v2")
    assert resolve_pdf_url("https://x.org/a/paper.PDF?dl=1", nope)[0] == "pdf"
    oa = lambda u: {"openAccessPdf": {"url": "https://oa.example/p.pdf"}} if "DOI:10.1/abc" in u else {}
    assert resolve_pdf_url("https://doi.org/10.1/abc", oa) == ("pdf", "https://oa.example/p.pdf")
    assert resolve_pdf_url("https://doi.org/10.9/zzz", oa) is None  # tidak open access
    assert resolve_pdf_url("https://blog.example/post", nope) == ("html", "https://blog.example/post")
    assert resolve_pdf_url("", nope) is None


def test_extract_pdf_text():
    assert "hello fulltext world" in extract_pdf_text(_pdf("hello fulltext world"))


def test_bm25_memilih_chunk_relevan():
    chunks = chunk_text(ISI.split("References")[0])
    top = bm25_rank(chunks, "cold start problem new user")
    assert top and "cold start" in chunks[top[0]]
    assert bm25_rank(chunks, "zzzz qqqq") == []


def test_fetch_cache_dan_buang_referensi(tmp_path):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return SimpleNamespace(ok=True, content=_pdf(ISI.replace("(", "").replace(")", "")[:1500]), json=lambda: {}, text="")

    ref = ReferenceItem(title="t", authors=["A B"], year=2024, link="https://arxiv.org/abs/2301.00001")
    t1 = fetch_fulltext(ref, tmp_path, fake_get)
    t2 = fetch_fulltext(ref, tmp_path, fake_get)  # dari cache
    assert t1 and t1 == t2 and len(calls) == 1
    assert fetch_fulltext(ReferenceItem(title="x", authors=[], year=2020, link=None), tmp_path, fake_get) is None


def test_fetch_gagal_tidak_melempar(tmp_path):
    def boom(url, **kw):
        raise ConnectionError("blocked")

    ref = ReferenceItem(title="t", authors=[], year=2024, link="https://arxiv.org/abs/1")
    assert fetch_fulltext(ref, tmp_path, boom) is None


def test_store_batas_budget_dan_tanpa_pengulangan():
    ref = ReferenceItem(title="Recommender systems", authors=["A B"], year=2024,
                        excerpt="collaborative filtering matrix factorization cold start")
    store = FullTextStore()
    store.texts[0] = ISI.split("References")[0]
    store._chunks[0] = chunk_text(store.texts[0])
    a = store.passages(0, ref, "cold start", budget_chars=700)
    b = store.passages(0, ref, "cold start", budget_chars=700)
    assert a and sum(map(len, a)) <= 700
    assert set(a).isdisjoint(b)  # chunk yang sudah dipakai tidak diulang
    assert store.passages(0, ref, "x", budget_chars=0) == []
