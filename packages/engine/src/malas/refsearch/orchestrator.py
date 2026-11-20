"""Orkestrator pencarian referensi: paralel antar sub-bab, fallback berantai, tidak pernah raise."""
import logging
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from malas.config import is_mock
from malas.crews.models.TaskOutput import ReferenceItem
from malas.refsearch.http import HttpClient
from malas.refsearch.models import Candidate, SectionQuery
from malas.refsearch.providers import FALLBACK_PROVIDERS, PROVIDERS, providers_for
from malas.refsearch.rank import choose, ckey, dedupe, is_valid, score

log = logging.getLogger("malas.refsearch")
PER_QUERY = 8


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def default_year_min() -> int:
    return _env_int("MALAS_REF_YEAR_MIN", time.localtime().tm_year - 10)


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
            http.stats[f"{name}:raw"] += len(found)
            for rank, c in enumerate(found):
                c.ranks = [rank]
                out.append(c)
    return out


def _search_section(http: HttpClient, sq: SectionQuery, judul: str, year_min: int, k: int,
                    names: List[str]) -> List[Candidate]:
    """Kandidat terbaik untuk satu sub-bab, dengan fallback bertahap bila hasil kurang dari k."""
    good: List[Candidate] = []

    def absorb(cands: List[Candidate], yr: int, overlap: int = 2) -> None:
        nonlocal good
        merged = dedupe(good + [c for c in cands if is_valid(c, yr)])
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
    return good


def search_references(
    plan: List[SectionQuery],
    judul: str,
    http: HttpClient,
    k: int = 2,
    year_min: Optional[int] = None,
    max_reuse: int = 2,
    workers: int = 4,
) -> Tuple[List[ReferenceItem], Dict]:
    """Kembalikan (referensi, laporan). Tidak pernah raise: kasus terburuk -> ([], laporan kosong)."""
    year_min = year_min or default_year_min()
    report: Dict = {"per_section": {}, "by_source": Counter(), "sections_without_refs": []}
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_search_section, http, sq, judul, year_min, k,
                                ["fixture"] if is_mock() else providers_for(sq.bidang, sq.indo)) for sq in plan]
            ranked: List[List[Candidate]] = []
            for f in futs:
                try:
                    ranked.append(f.result(timeout=120))
                except Exception:
                    ranked.append([])
    except Exception:
        return [], report

    used: Counter = Counter()
    chosen: Dict[str, Candidate] = {}
    order: List[str] = []
    for sq, cands in zip(plan, ranked):
        picked = choose(cands, k, used, max_reuse)
        report["per_section"][sq.section] = len(picked)
        if not picked:
            report["sections_without_refs"].append(sq.section)
        for c in picked:
            key = ckey(c)
            if key in chosen:
                c = chosen[key]
            else:
                chosen[key] = c
                order.append(key)
                c.sections = []
            if sq.section not in c.sections:
                c.sections.append(sq.section)

    refs: List[ReferenceItem] = []
    for key in order:
        c = chosen[key]
        refs.append(ReferenceItem(
            title=c.title, authors=c.authors[:6], year=int(c.year or 0), link=c.url or (f"https://doi.org/{c.doi}" if c.doi else None),
            excerpt=(c.abstract[:900] if c.abstract else None), doi=c.doi, source="+".join(sorted(c.sources)),
            source_id=c.source_id, oa_pdf_url=c.oa_pdf_url, venue=c.venue, sections=list(c.sections),
        ))
        for s in c.sources:
            report["by_source"][s] += 1
    report["by_source"] = dict(report["by_source"])
    report["http_calls"], report["cache_hits"] = http.calls, http.cache_hits
    report["diagnostik"] = dict(sorted(http.stats.items()))
    return refs, report
