"""Orkestrator pencarian referensi: paralel antar sub-bab, fallback berantai, tidak pernah raise."""
import dataclasses
import logging
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Callable, Dict, List, Optional, Tuple

from malas.config import is_mock
from malas.crews.models.TaskOutput import ReferenceItem
from malas.fulltext import _tokens
from malas.names import normalize_author
from malas.refsearch.http import HttpClient
from malas.refsearch.models import Candidate, SectionQuery
from malas.refsearch.providers import FALLBACK_PROVIDERS, PROVIDERS, providers_for
from malas.refsearch.rank import CLASSIC_CITES, choose, ckey, dedupe, is_valid, score
from malas.refsearch.select_llm import rerank as llm_rerank

log = logging.getLogger("malas.refsearch")
PER_QUERY = 8
LANDMARK_CITES = CLASSIC_CITES  # ambang "karya dasar" (cited_by), sama dengan pengecualian batas tahun
LANDMARK_PER_QUERY = 10
K_LANDMARK, K_RECENT = 3, 2  # k adaptif: sub-bab konsep/teori & 1.1 vs sub-bab lain


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def default_year_min() -> int:
    return _env_int("MALAS_REF_YEAR_MIN", time.localtime().tm_year - 10)


def k_for(sq: SectionQuery, k: Optional[int] = None) -> int:
    """k eksplisit dihormati; selain itu adaptif: 3 untuk sub-bab konsep/teori & 1.1, 2 lainnya."""
    if k is not None:
        return k
    return K_LANDMARK if sq.role == "landmark" else K_RECENT


def _gather(http: HttpClient, sq: SectionQuery, provider_names: List[str], year_min: int,
            queries: Optional[List[Tuple[str, str]]] = None) -> List[Candidate]:
    out: List[Candidate] = []
    for name in provider_names:
        prov = PROVIDERS.get(name)
        if prov is None:
            continue
        for lang, q in (queries if queries is not None else sq.queries()):
            try:
                found = prov.search(http, q, lang, PER_QUERY, year_min)
            except Exception as e:
                log.warning("provider %s gagal: %s", name, e.__class__.__name__)
                found = []
            http.bump(f"{name}:raw", len(found))
            for rank, c in enumerate(found):
                c.ranks = [rank]
                out.append(c)
    return out


# --------------------------------------------------------------------------- pass landmark (karya dasar)
def landmark_queries(sq: SectionQuery) -> List[str]:
    """Query pass landmark: gabungan dua konsep pertama (lebih spesifik), lalu tiap konsep sendiri."""
    t = [x for x in sq.landmark_terms if x.strip()][:2]
    return ([" ".join(t)] if len(t) == 2 else []) + t


class _Memo:
    """Hasil query landmark dibagi antar sub-bab dalam satu pencarian (konsep sama -> 1 request)."""

    def __init__(self):
        self.lock, self.data = threading.Lock(), {}

    def get(self, key, fn: Callable[[], List[Candidate]]) -> List[Candidate]:
        with self.lock:
            if key in self.data:
                return self.data[key]
        val = fn()
        with self.lock:
            return self.data.setdefault(key, val)


def rank_landmarks(cands: List[Candidate], sq: SectionQuery) -> List[Candidate]:
    """Saring & urutkan karya dasar: kutipan >= LANDMARK_CITES dan salah satu konsep utuh ada di JUDUL.

    Urutan: banyaknya konsep yang muncul di judul+abstrak, lalu jumlah kutipan.
    """
    terms = [t for t in (set(_tokens(x)) for x in sq.landmark_terms) if t]
    keep = []
    for c in dedupe(cands):
        if c.cited_by < LANDMARK_CITES or not is_valid(c, 0) or not (c.url or c.doi):
            continue
        title = set(_tokens(c.title))
        if not any(t <= title for t in terms):  # konsep hanya disebut sambil lalu di abstrak -> bukan karya dasarnya
            continue
        body = title | set(_tokens(c.abstract or ""))
        keep.append((sum(1 for t in terms if t <= body), c.cited_by, c))
    keep.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [c for _, _, c in keep]


def _landmarks(http: HttpClient, sq: SectionQuery, names: List[str], memo: _Memo) -> List[Candidate]:
    """Pass karya dasar (hanya role='landmark'): query Inggris per konsep, tanpa batas tahun, urut jumlah kutipan."""
    if sq.role != "landmark" or not sq.landmark_terms:
        return []
    out: List[Candidate] = []
    for name in names:
        fn = getattr(PROVIDERS.get(name), "landmark_search", None)
        if fn is None:
            continue
        for q in landmark_queries(sq):
            def run(fn=fn, q=q, name=name) -> List[Candidate]:
                try:
                    found = fn(http, q, LANDMARK_PER_QUERY)
                except Exception as e:
                    log.warning("landmark %s gagal: %s", name, e.__class__.__name__)
                    found = []
                http.bump(f"{name}:landmark_raw", len(found))
                return found

            for rank, c in enumerate(memo.get((name, q.lower()), run)):
                # salinan per sub-bab: dedupe/_merge memodifikasi objek, jangan bocor ke sub-bab lain
                out.append(dataclasses.replace(c, ranks=[rank], sources=set(c.sources), sections=[]))
    return rank_landmarks(out, sq)


# --------------------------------------------------------------------------- per sub-bab
def _search_section(http: HttpClient, sq: SectionQuery, judul: str, year_min: int, k: int,
                    names: List[str], memo: Optional[_Memo] = None) -> Tuple[List[Candidate], List[Candidate]]:
    """(kandidat terbaik, karya dasar) untuk satu sub-bab, dengan fallback bertahap bila hasil kurang dari k."""
    lms = _landmarks(http, sq, names, memo or _Memo())
    good: List[Candidate] = []

    def absorb(cands: List[Candidate], yr: int, overlap: Optional[int] = None) -> None:
        nonlocal good
        merged = dedupe(good + [c for c in cands if is_valid(c, yr) and (c.url or c.doi)])  # tanpa tautan = tak bisa dikutip
        good = score(merged, sq, min_overlap=overlap)

    absorb(_gather(http, sq, names, year_min), year_min)
    if len(good) < k:  # 1) longgarkan batas tahun
        absorb(_gather(http, sq, names, year_min - 10), year_min - 10)
    if len(good) < k:  # 2) query dari judul makalah saja (sub-bab generik / topik sempit)
        broad = SectionQuery(section=sq.section, q_en="", q_id=judul, bidang=sq.bidang, indo=sq.indo)
        absorb(_gather(http, broad, names, year_min - 10, broad.queries()), year_min - 10, overlap=1)
    if len(good) < k and not is_mock():  # 3) topik tanpa literatur jurnal: ensiklopedia & buku, urutan terakhir
        extra = [n for n in FALLBACK_PROVIDERS if n not in names]
        absorb(_gather(http, sq, extra, year_min), year_min)
        if len(good) < k:
            broad = SectionQuery(section=sq.section, q_en="", q_id=judul, bidang=sq.bidang, indo=sq.indo)
            absorb(_gather(http, broad, extra, year_min, broad.queries()), year_min, overlap=1)
    return good, lms


def _pick(cands: List[Candidate], lms: List[Candidate], k: int, used: Counter, max_reuse: int) -> List[Candidate]:
    """Wajib >=1 karya dasar bila tersedia (tetap tunduk max_reuse), sisanya dari kandidat biasa."""
    picked = choose(lms, 1, used, max_reuse) if lms and k > 0 else []
    have = {ckey(c) for c in picked}
    return picked + choose([c for c in cands if ckey(c) not in have], k - len(picked), used, max_reuse)


def _lang_ratio(cands: List[Candidate]) -> Dict[str, float]:
    """Proporsi bahasa referensi terpilih; 'unknown' = sumber tak memberi bahasa (mis. Crossref)."""
    cnt = Counter((c.language or "unknown") for c in cands)
    return {lang: round(v / len(cands), 3) for lang, v in cnt.most_common()} if cands else {}


def search_references(
    plan: List[SectionQuery],
    judul: str,
    http: HttpClient,
    k: Optional[int] = None,
    year_min: Optional[int] = None,
    max_reuse: int = 2,
    workers: int = 4,
    rerank: Optional[Callable[[str], str]] = None,
    deadline: Optional[float] = None,
) -> Tuple[List[ReferenceItem], Dict]:
    """Kembalikan (referensi, laporan). Tidak pernah raise: kasus terburuk -> ([], laporan kosong).

    k=None -> adaptif per sub-bab (`k_for`) lalu isi ulang bergiliran sampai `MALAS_REF_TARGET` (default 12)
    referensi unik selama kandidat masih ada; k eksplisit -> tepat k per sub-bab (perilaku lama).
    `max_reuse` selalu dihormati. Laporan memuat `language_ratio` dan `landmark_count`.
    """
    year_min = year_min or default_year_min()
    report: Dict = {"per_section": {}, "by_source": Counter(), "sections_without_refs": [], "k_per_section": {}}
    deadline = deadline if deadline is not None else float(_env_int("MALAS_REFSEARCH_TIMEOUT", 150))
    memo = _Memo()
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futs = [pool.submit(_search_section, http, sq, judul, year_min, k_for(sq, k),
                            ["fixture"] if is_mock() else providers_for(sq.bidang, sq.indo), memo) for sq in plan]
        done, _ = wait(futs, timeout=deadline)  # tenggat GLOBAL: yang belum selesai ditinggalkan, sisanya tetap dipakai
        ranked: List[Tuple[List[Candidate], List[Candidate]]] = []
        for f in futs:
            try:
                ranked.append(f.result() if f in done else ([], []))
            except Exception:
                ranked.append(([], []))
    except Exception:
        return [], report
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    used: Counter = Counter()
    chosen: Dict[str, Candidate] = {}
    order: List[str] = []
    rest: List[Tuple[SectionQuery, List[Candidate]]] = []  # sisa kandidat per sub-bab untuk isi ulang target

    def attach(sq: SectionQuery, c: Candidate) -> None:
        key = ckey(c)
        if key in chosen:
            c = chosen[key]
        else:
            chosen[key] = c
            order.append(key)
            c.sections = []
        if sq.section not in c.sections:
            c.sections.append(sq.section)

    for sq, (cands, lms) in zip(plan, ranked):
        kk = k_for(sq, k)
        report["k_per_section"][sq.section] = kk
        if rerank is not None and cands:
            cands = llm_rerank(sq, judul, cands, kk, rerank)  # LLM hanya memilih ID; gagal = urutan semula
        picked = _pick(cands, lms, kk, used, max_reuse)
        report["per_section"][sq.section] = len(picked)
        if not picked:
            report["sections_without_refs"].append(sq.section)
        for c in picked:
            attach(sq, c)
        have = {ckey(c) for c in picked}
        rest.append((sq, [c for c in cands if ckey(c) not in have]))

    target = _env_int("MALAS_REF_TARGET", 12) if k is None else 0
    while len(order) < target:  # bergiliran 1 per sub-bab per putaran; hanya paper baru, tetap tunduk max_reuse
        maju = False
        for sq, cands in rest:
            if len(order) >= target:
                break
            extra = choose([c for c in cands if ckey(c) not in chosen], 1, used, max_reuse)
            if extra:
                attach(sq, extra[0])
                cands.remove(extra[0])
                report["per_section"][sq.section] += 1
                maju = True
        if not maju:
            break
    if target:
        report["sections_without_refs"] = [s for s in report["sections_without_refs"] if not report["per_section"][s]]

    refs: List[ReferenceItem] = []
    picked_all = [chosen[key] for key in order]
    for c in picked_all:
        refs.append(ReferenceItem(
            title=c.title, authors=[n for n in (normalize_author(x) for x in c.authors[:6]) if n], year=int(c.year or 0), link=c.url or (f"https://doi.org/{c.doi}" if c.doi else None),
            excerpt=(c.abstract[:900] if c.abstract else None), doi=c.doi, source="+".join(sorted(c.sources)),
            source_id=c.source_id, oa_pdf_url=c.oa_pdf_url, venue=c.venue, sections=list(c.sections),
            volume=c.volume, issue=c.issue, pages=c.pages,
        ))
        for s in c.sources:
            report["by_source"][s] += 1
    report["by_source"] = dict(report["by_source"])
    report["language_ratio"] = _lang_ratio(picked_all)
    report["landmark_count"] = sum(1 for c in picked_all if c.cited_by >= LANDMARK_CITES)
    report["landmarks"] = [f"{c.title[:80]} ({c.year}; {c.cited_by} kutipan)" for c in picked_all
                           if c.cited_by >= LANDMARK_CITES]
    report["http_calls"], report["cache_hits"] = http.calls, http.cache_hits
    report["diagnostik"] = dict(sorted(http.stats.items()))
    return refs, report
