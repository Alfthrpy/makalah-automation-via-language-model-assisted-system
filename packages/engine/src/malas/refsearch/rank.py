"""Dedupe, skoring, dan seleksi kandidat. Murni kode, tanpa LLM/jaringan."""
import difflib
import math
import re
import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Optional, Set

from malas.fulltext import _tokens
from malas.refsearch.models import Candidate, SectionQuery

MIN_TITLE_WORDS = 3
CLASSIC_CITES = 300  # karya sangat banyak dikutip boleh lebih tua dari batas tahun
_BAD_TITLE = re.compile(r"^(?:table of contents|front matter|back matter|cover|editorial|erratum|correction|"
                        r"daftar isi|sampul)\b", re.I)


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def ckey(c: Candidate) -> str:
    """Identitas paper lintas sub-bab: DOI bila ada, selain itu judul ternormalisasi."""
    return f"doi:{c.doi}" if c.doi else f"t:{norm_title(c.title)}"


def _merge(into: Candidate, other: Candidate) -> None:
    """Gabungkan duplikat: simpan data terlengkap."""
    if len(other.abstract or "") > len(into.abstract or ""):
        into.abstract = other.abstract
    for f in ("doi", "url", "venue", "language", "oa_pdf_url", "year"):
        if not getattr(into, f) and getattr(other, f):
            setattr(into, f, getattr(other, f))
    if len(other.authors) > len(into.authors):
        into.authors = other.authors
    into.cited_by = max(into.cited_by, other.cited_by)
    into.ranks += other.ranks
    into.sources |= other.sources
    for s in other.sections:
        if s not in into.sections:
            into.sections.append(s)


def dedupe(cands: Iterable[Candidate], pool: Optional[Dict[str, Candidate]] = None) -> List[Candidate]:
    """Gabungkan duplikat (DOI, lalu judul ternormalisasi + tahun±1, lalu kemiripan judul > 0.93).

    `pool` (opsional) dibagi antar sub-bab agar paper yang sama dikenali sebagai satu objek.
    """
    pool = pool if pool is not None else {}
    out: List[Candidate] = []
    for c in cands:
        nt = norm_title(c.title)
        if not nt:
            continue
        hit = pool.get(f"doi:{c.doi}") if c.doi else None
        if hit is None:
            for k in (f"t:{nt}",):
                h = pool.get(k)
                if h and (not h.year or not c.year or abs(h.year - c.year) <= 1):
                    hit = h
                    break
        if hit is None and len(nt) > 25:  # kemiripan hanya untuk judul cukup panjang (hindari salah gabung)
            for h in {id(v): v for v in pool.values()}.values():
                nh = norm_title(h.title)
                same_nums = re.findall(r"\d+", nh) == re.findall(r"\d+", nt)  # "Bagian 1" != "Bagian 2"
                if same_nums and abs(len(nh) - len(nt)) < 8 and difflib.SequenceMatcher(None, nh, nt).ratio() > 0.93:
                    hit = h
                    break
        if hit is not None:
            _merge(hit, c)
            if not any(x is hit for x in out):
                out.append(hit)
            if c.doi and f"doi:{c.doi}" not in pool:
                pool[f"doi:{c.doi}"] = hit
            continue
        pool[f"t:{nt}"] = c
        if c.doi:
            pool[f"doi:{c.doi}"] = c
        out.append(c)
    return out


# --------------------------------------------------------------------------- skor
def _bm25(docs: List[List[str]], q: Set[str], k1: float = 1.5, b: float = 0.75) -> List[float]:
    if not docs:
        return []
    tfs = [Counter(d) for d in docs]
    avg = sum(len(d) for d in docs) / len(docs) or 1
    df = Counter(t for tf in tfs for t in tf)
    n = len(docs)
    scores = []
    for tf, d in zip(tfs, docs):
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    return scores


def query_tokens(sq: SectionQuery) -> Set[str]:
    return set(_tokens(f"{sq.q_en} {sq.q_id}"))


_BAD_FILE = re.compile(r"/(?:cover|abstrak|abstract|daftar[-_ ]?isi|toc|sampul)\.pdf(?:\?|$)", re.I)


def is_valid(c: Candidate, year_min: int) -> bool:
    if not c.year or _BAD_TITLE.match(c.title):
        return False
    if _BAD_FILE.search(c.url or "") or _BAD_FILE.search(c.oa_pdf_url or ""):  # repositori kampus: file sampul/abstrak saja
        return False
    if c.kind == "encyclopedia":  # judul artikel pendek ("Majapahit") wajar
        return True
    if len(c.title.split()) < MIN_TITLE_WORDS:
        return False
    return c.year >= year_min or c.cited_by >= CLASSIC_CITES or c.kind == "book"  # buku boleh lebih tua


def adaptive_overlap(n_query_tokens: int) -> int:
    """Jumlah kata kunci query yang wajib muncul di judul+abstrak: ±60% (min 2, maks 4)."""
    return max(2, min(4, math.ceil(0.6 * n_query_tokens)))


def score(cands: List[Candidate], sq: SectionQuery, min_overlap: Optional[int] = None) -> List[Candidate]:
    """Urutkan kandidat; kandidat dengan kata kunci query terlalu sedikit dibuang (tidak relevan).

    min_overlap=None -> adaptif (lihat adaptive_overlap); fallback memanggil dengan 1 untuk melonggarkan.
    """
    q = query_tokens(sq)
    if not cands or not q:
        return []
    need = min(min_overlap if min_overlap is not None else adaptive_overlap(len(q)), len(q))
    docs, keep = [], []
    for c in cands:
        toks = _tokens(c.title) * 2 + _tokens(c.abstract or "")  # judul berbobot 2x
        if len(q & set(toks)) >= need:
            docs.append(toks)
            keep.append(c)
    if not keep:
        return []
    rel = _bm25(docs, q)
    top_rel = max(rel) or 1.0
    rrf = [sum(1 / (60 + r) for r in c.ranks) for c in keep]
    top_rrf = max(rrf) or 1.0
    final = []
    for c, r, f in zip(keep, rel, rrf):
        prior = (0.3 if c.abstract else 0.0) + (0.2 if c.oa_pdf_url else 0.0) + (0.15 if c.doi else 0.0) \
            + min(0.3, 0.06 * math.log1p(c.cited_by)) + (0.1 if len(c.sources) > 1 else 0.0) \
            + (0.3 if sq.indo and (c.language or "") == "id" else 0.0) \
            - (0.4 if c.kind == "encyclopedia" else 0.0)
        final.append((0.5 * r / top_rel + 0.3 * f / top_rrf + 0.2 * max(min(prior, 1.0), -0.5), c))
    final.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in final]


def choose(ranked: List[Candidate], k: int, used: Counter, max_reuse: int = 2) -> List[Candidate]:
    """Pilih k terbaik; satu paper dipakai paling banyak `max_reuse` sub-bab agar referensi beragam."""
    picked: List[Candidate] = []
    for c in ranked:
        if used[ckey(c)] >= max_reuse or any(ckey(p) == ckey(c) for p in picked):
            continue
        picked.append(c)
        if len(picked) == k:
            break
    for c in picked:
        used[ckey(c)] += 1
    return picked
