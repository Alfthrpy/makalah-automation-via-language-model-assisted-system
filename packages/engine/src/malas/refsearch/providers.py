"""Provider pencarian. Tiap provider: search(http, query, lang, limit, year_min) -> list[Candidate].

Aturan: tidak pernah raise; bila respons gagal/aneh -> []. Hanya field dari respons API yang dipakai.
Catatan: bentuk respons ditulis berdasarkan dokumentasi publik dan belum diuji ke API sungguhan dari sandbox ini;
tes memakai fixture. Jalankan `python -m malas.refsearch` di mesin dengan internet untuk memverifikasi.
"""
import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from urllib.parse import quote

from malas.refsearch.models import Candidate

_TAG = re.compile(r"<[^>]+>")


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    m = re.search(r"10\.\d{4,9}/\S+", doi.strip())
    return m.group(0).rstrip(".,;)").lower() if m else None


def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = html.unescape(_TAG.sub(" ", s))
    s = re.sub(r"^\s*abstract\s*[:.\-]?\s*", "", " ".join(s.split()), flags=re.I)
    return s or None


def _year(v) -> Optional[int]:
    try:
        y = int(str(v)[:4])
        return y if 1800 < y < 2200 else None
    except (TypeError, ValueError):
        return None


def _doi_url(doi: Optional[str]) -> Optional[str]:
    return f"https://doi.org/{doi}" if doi else None


def _str(v) -> Optional[str]:
    """Nilai bibliografis (volume/issue) sebagai string bersih; kosong -> None."""
    s = " ".join(str(v).split()) if v is not None else ""
    return s or None


def page_range(first=None, last=None) -> Optional[str]:
    """Rentang halaman APA: "36–52" (en dash); satu halaman bila first == last atau last kosong.

    `first` boleh berupa rentang utuh ("36-52", gaya Crossref/Europe PMC); tanda hubung diganti en dash.
    """
    a, b = _str(first), _str(last)
    if a and not b and re.fullmatch(r"\w+\s*[-\u2010-\u2014]+\s*\w+", a):
        a, b = (x.strip() for x in re.split(r"[-\u2010-\u2014]+", a, maxsplit=1))
    if not a:
        return b
    return a if not b or a == b else f"{a}\u2013{b}"


# --------------------------------------------------------------------------- OpenAlex
def _inverted_abstract(inv) -> Optional[str]:
    if not isinstance(inv, dict) or not inv:
        return None
    slots: Dict[int, str] = {}
    for word, positions in inv.items():
        for p in positions or []:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots)) or None


class OpenAlex:
    name = "openalex"
    URL = "https://api.openalex.org/works"
    SELECT = ("id,doi,title,publication_year,authorships,primary_location,best_oa_location,"
              "abstract_inverted_index,cited_by_count,language,type,biblio")
    SKIP_TYPES = {"paratext", "erratum", "dataset", "peer-review", "editorial", "letter", "retraction"}

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        flt = f"from_publication_date:{year_min}-01-01,is_retracted:false"
        if lang == "id":
            flt += ",language:id"
        params = {"search": query, "filter": flt, "per-page": limit, "select": self.SELECT}
        if os.getenv("MALAS_OPENALEX_API_KEY"):
            params["api_key"] = os.environ["MALAS_OPENALEX_API_KEY"]
        if http.contact:
            params["mailto"] = http.contact
        data = http.get_json(self.URL, params)
        out: List[Candidate] = []
        for w in ((data or {}).get("results") or []) if isinstance(data, dict) else []:
            if w.get("type") in self.SKIP_TYPES or not w.get("title"):
                continue
            doi = normalize_doi(w.get("doi"))
            loc = w.get("primary_location") or {}
            best = w.get("best_oa_location") or {}
            bib = w.get("biblio") or {}
            out.append(Candidate(
                source=self.name, source_id=str(w.get("id") or ""), title=clean_text(w["title"]) or "",
                authors=[a["author"]["display_name"] for a in w.get("authorships", [])
                         if (a.get("author") or {}).get("display_name")][:8],
                year=_year(w.get("publication_year")), doi=doi,
                url=_doi_url(doi) or loc.get("landing_page_url"),
                abstract=_inverted_abstract(w.get("abstract_inverted_index")),
                venue=(loc.get("source") or {}).get("display_name"),
                language=w.get("language"), cited_by=int(w.get("cited_by_count") or 0),
                oa_pdf_url=best.get("pdf_url"), volume=_str(bib.get("volume")), issue=_str(bib.get("issue")),
                pages=page_range(bib.get("first_page"), bib.get("last_page")),
            ))
        return out


# --------------------------------------------------------------------------- Crossref
class Crossref:
    name = "crossref"
    URL = "https://api.crossref.org/works"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        params = {
            "query.bibliographic": query, "rows": limit,
            "filter": f"from-pub-date:{year_min},type:journal-article",
            "select": "DOI,title,author,issued,container-title,abstract,URL,is-referenced-by-count,volume,issue,page",
        }
        if http.contact:
            params["mailto"] = http.contact
        data = http.get_json(self.URL, params)
        items = (((data or {}).get("message") or {}).get("items") or []) if isinstance(data, dict) else []
        out: List[Candidate] = []
        for it in items:
            titles = it.get("title") or []
            if not titles:
                continue
            doi = normalize_doi(it.get("DOI"))
            parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
            authors = [(f'{a["family"]}, {a["given"]}' if a.get("family") and a.get("given")
                        else (a.get("family") or a.get("given") or a.get("name") or ""))
                       for a in it.get("author", [])][:8]  # "Family, Given": informasi keluarga tidak hilang (names.py)
            out.append(Candidate(
                source=self.name, source_id=doi or "", title=clean_text(titles[0]) or "",
                authors=[a for a in authors if a], year=_year(parts[0] if parts else None), doi=doi,
                url=_doi_url(doi) or it.get("URL"), abstract=clean_text(it.get("abstract")),
                venue=(it.get("container-title") or [None])[0], language=None,
                cited_by=int(it.get("is-referenced-by-count") or 0),
                volume=_str(it.get("volume")), issue=_str(it.get("issue")), pages=page_range(it.get("page")),
            ))
        return out


# --------------------------------------------------------------------------- Europe PMC
def _flip_initials(name: str) -> str:
    """'Smith JA' -> 'JA Smith' agar nama belakang jadi token terakhir (dibaca citations.py)."""
    toks = name.strip().rstrip(".").split()
    if len(toks) >= 2 and toks[-1].isupper() and len(toks[-1]) <= 3:
        return f"{toks[-1]} {' '.join(toks[:-1])}"
    return " ".join(toks)


class EuropePMC:
    name = "europepmc"
    URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        q = re.sub(r"[^\w\s\-]", " ", query)
        params = {"query": f"({q}) AND PUB_YEAR:[{year_min} TO 3000]", "format": "json",
                  "resultType": "core", "pageSize": limit}
        data = http.get_json(self.URL, params)
        out: List[Candidate] = []
        for r in (((data or {}).get("resultList") or {}).get("result") or []) if isinstance(data, dict) else []:
            if not r.get("title"):
                continue
            doi = normalize_doi(r.get("doi"))
            names = [" ".join(x for x in (a.get("firstName"), a.get("lastName")) if x) or a.get("fullName", "")
                     for a in ((r.get("authorList") or {}).get("author") or [])]
            if not any(names) and r.get("authorString"):
                names = [_flip_initials(n) for n in r["authorString"].split(", ")]
            pdf = None
            for ft in ((r.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
                if ft.get("documentStyle") == "pdf" and ft.get("availability") in ("Free", "Open access"):
                    pdf = ft.get("url")
                    break
            pid = f"{r.get('source', '')}:{r.get('id', '')}"
            ji = r.get("journalInfo") or {}  # resultType=core menaruh volume/issue di sini; "lite" di tingkat atas
            out.append(Candidate(
                source=self.name, source_id=pid, title=clean_text(r["title"]) or "",
                authors=[n for n in names if n][:8], year=_year(r.get("pubYear")), doi=doi,
                url=_doi_url(doi) or (f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}"),
                abstract=clean_text(r.get("abstractText")), venue=r.get("journalTitle"),
                language=(r.get("language") or "")[:2] or None, cited_by=int(r.get("citedByCount") or 0),
                oa_pdf_url=pdf, volume=_str(r.get("journalVolume") or ji.get("volume")),
                issue=_str(r.get("issue") or ji.get("issue")),
                pages=page_range(r.get("pageInfo")),
            ))
        return out


# --------------------------------------------------------------------------- arXiv
_NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


class ArXiv:
    name = "arxiv"
    URL = "https://export.arxiv.org/api/query"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        if lang == "id":
            return []  # arXiv hampir seluruhnya Inggris
        terms = re.findall(r"[A-Za-z]{3,}", query)[:6]
        if not terms:
            return []
        params = {"search_query": " AND ".join(f"all:{t}" for t in terms), "start": 0,
                  "max_results": limit, "sortBy": "relevance"}
        text = http.get_text(self.URL, params)
        if not text:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        out: List[Candidate] = []
        for e in root.findall("a:entry", _NS):
            get = lambda tag: (e.findtext(tag, default="", namespaces=_NS) or "").strip()
            aid = get("a:id")
            year = _year(get("a:published"))
            title = clean_text(get("a:title"))
            if not title or not year or year < year_min:
                continue
            m = re.search(r"arxiv\.org/abs/(.+)$", aid)
            doi = normalize_doi(get("x:doi"))
            out.append(Candidate(
                source=self.name, source_id=m.group(1) if m else aid, title=title,
                authors=[(a.findtext("a:name", default="", namespaces=_NS) or "").strip()
                         for a in e.findall("a:author", _NS)][:8],
                year=year, doi=doi, url=aid.replace("http://", "https://"),
                abstract=clean_text(get("a:summary")), venue="arXiv", language="en",
                oa_pdf_url=f"https://arxiv.org/pdf/{m.group(1)}" if m else None,
            ))
        return out


# --------------------------------------------------------------------------- DOAJ
class DOAJ:
    name = "doaj"
    URL = "https://doaj.org/api/search/articles/"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        q = re.sub(r"[^\w\s]", " ", query).strip()
        if not q:
            return []
        data = http.get_json(self.URL + quote(q, safe=""), {"pageSize": limit})
        out: List[Candidate] = []
        for r in ((data or {}).get("results") or []) if isinstance(data, dict) else []:
            b = r.get("bibjson") or {}
            year = _year(b.get("year"))
            if not b.get("title") or not year or year < year_min:
                continue
            doi = normalize_doi(next((i.get("id") for i in b.get("identifier", []) if i.get("type") == "doi"), None))
            link = next((l.get("url") for l in b.get("link", []) if l.get("type") == "fulltext"), None)
            j = b.get("journal") or {}
            out.append(Candidate(
                source=self.name, source_id=str(r.get("id") or ""), title=clean_text(b["title"]) or "",
                authors=[a.get("name", "") for a in b.get("author", []) if a.get("name")][:8],
                year=year, doi=doi, url=_doi_url(doi) or link, abstract=clean_text(b.get("abstract")),
                venue=j.get("title"), language=((j.get("language") or [""])[0] or "").lower()[:2] or None,
                oa_pdf_url=link if link and link.lower().split("?")[0].endswith(".pdf") else None,
            ))
        return out


# --------------------------------------------------------------------------- Wikipedia (fallback topik populer/sejarah)
class Wikipedia:
    """Ringkasan pembuka artikel. Dipakai HANYA sebagai fallback; kredibilitas akademiknya rendah (kind=encyclopedia)."""

    name = "wikipedia"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        wl = "id" if lang == "id" else "en"
        params = {
            "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrlimit": min(limit, 5),
            "prop": "extracts|info", "exintro": 1, "explaintext": 1, "exchars": 900, "inprop": "url", "redirects": 1,
        }
        data = http.get_json(f"https://{wl}.wikipedia.org/w/api.php", params)
        pages = (((data or {}).get("query") or {}).get("pages") or {}) if isinstance(data, dict) else {}
        out: List[Candidate] = []
        for pg in sorted((p for p in pages.values() if isinstance(p, dict)), key=lambda p: p.get("index", 99)):
            extract = clean_text(pg.get("extract"))
            if not pg.get("title") or not extract or len(extract) < 80:
                continue
            out.append(Candidate(
                source=self.name, source_id=f"{wl}:{pg.get('pageid')}", title=pg["title"], authors=["Wikipedia"],
                year=_year(pg.get("touched")), url=pg.get("fullurl"), abstract=extract,
                venue=f"Wikipedia ({wl})", language=wl, kind="encyclopedia",
            ))
        return out


# --------------------------------------------------------------------------- Open Library (buku)
class OpenLibrary:
    name = "openlibrary"
    URL = "https://openlibrary.org/search.json"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        params = {"q": query, "limit": limit, "fields": "key,title,author_name,first_publish_year,language"}
        data = http.get_json(self.URL, params)
        out: List[Candidate] = []
        for d in ((data or {}).get("docs") or []) if isinstance(data, dict) else []:
            if not d.get("title") or not d.get("author_name") or not d.get("key"):
                continue
            out.append(Candidate(
                source=self.name, source_id=str(d["key"]), title=clean_text(d["title"]) or "",
                authors=list(d["author_name"])[:4], year=_year(d.get("first_publish_year")),
                url=f"https://openlibrary.org{d['key']}", kind="book",
                language=((d.get("language") or [""])[0] or "")[:2] or None,
            ))
        return out


# --------------------------------------------------------------------------- fixture (mode mock, tanpa HTTP)
class Fixture:
    """Hasil deterministik untuk MALAS_MOCK=1 dan tes alur: tanpa jaringan sama sekali."""

    name = "fixture"

    def search(self, http, query: str, lang: str, limit: int, year_min: int) -> List[Candidate]:
        words = [w for w in re.findall(r"[A-Za-z]{4,}", query)][:4] or ["topik"]
        h = int(hashlib.sha1(query.encode()).hexdigest()[:6], 16)  # deterministik antar proses
        out = []
        for i in range(min(limit, 4)):
            w = words[i % len(words)].capitalize()
            out.append(Candidate(
                source=self.name, source_id=f"fx-{h}-{i}",
                title=f"Kajian {w} dan {' '.join(words[:2])} ({i + 1})",
                authors=[f"Penulis{chr(65 + i)} Fixture"], year=max(year_min, 2020) + i % 4,
                doi=f"10.0000/fixture.{h}.{i}", url=None,
                abstract=f"Penelitian ini membahas {query}. " * 3, venue="Jurnal Fixture", language=lang,
                cited_by=i,
            ))
        return out


PROVIDERS: Dict[str, object] = {
    p.name: p for p in (OpenAlex(), Crossref(), EuropePMC(), ArXiv(), DOAJ(), Wikipedia(), OpenLibrary(), Fixture())
}
FALLBACK_PROVIDERS = ["wikipedia", "openlibrary"]  # hanya dipakai bila sumber akademik belum cukup

# Bidang -> provider tambahan (OpenAlex & Crossref selalu dipakai)
FIELD_PROVIDERS: Dict[str, List[str]] = {
    "medis": ["europepmc"],
    "teknik": ["arxiv"],
    "sains": ["arxiv"],
}
INDO_PROVIDERS = ["doaj"]
BASE_PROVIDERS = ["openalex", "crossref"]


def providers_for(bidang: str, indo: bool) -> List[str]:
    names = list(BASE_PROVIDERS) + FIELD_PROVIDERS.get(bidang, []) + (INDO_PROVIDERS if indo else [])
    return list(dict.fromkeys(names))
