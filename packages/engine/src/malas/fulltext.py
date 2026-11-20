"""Full-text referensi yang hemat token: unduh + ekstrak dengan kode biasa, lalu pilih
hanya beberapa kutipan relevan per sub-bab lewat BM25 (kata kunci). Tanpa LLM/embedding.

Alur:  link referensi -> URL PDF open-access -> teks (cache di disk) -> potongan (chunk)
       -> BM25 terhadap (judul sub-bab + judul makalah + judul/abstrak referensi)
       -> top-N chunk dalam batas karakter, tanpa mengulang chunk yang sudah dipakai.
"""
import hashlib
import io
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import requests

from malas.crews.models.TaskOutput import ReferenceItem

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 25
CHUNK_CHARS = 600
_UA = {"User-Agent": "malas-research-tool/0.1"}
_STOP = set(
    "the of and to in a is that for on with as are by be this it from or an at which we can has have was were not "
    "yang dan di ke dari untuk pada dengan ini itu adalah dalam sebagai oleh atau juga akan dapat para suatu".split()
)


# --------------------------------------------------------------------------- resolusi URL
def resolve_pdf_url(link: str, get_json: Callable[[str], Optional[dict]]) -> Optional[Tuple[str, str]]:
    """Kembalikan (jenis, url) dengan jenis 'pdf' atau 'html', atau None bila tidak bisa."""
    if not link:
        return None
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?$", link)
    if m:
        return "pdf", f"https://arxiv.org/pdf/{m.group(1)}"
    if link.lower().split("?")[0].endswith(".pdf"):
        return "pdf", link
    api = "https://api.semanticscholar.org/graph/v1/paper/{}?fields=openAccessPdf"
    ident = None
    if "doi.org/" in link:
        ident = "DOI:" + link.split("doi.org/", 1)[1]
    elif "semanticscholar.org/paper/" in link:
        ident = link.rstrip("/").rsplit("/", 1)[1]
    if ident:
        data = get_json(api.format(ident)) or {}
        pdf = (data.get("openAccessPdf") or {}).get("url")
        return ("pdf", pdf) if pdf else None
    return "html", link


def _default_get(url: str, **kw) -> requests.Response:
    return requests.get(url, headers=_UA, timeout=20, **kw)


# --------------------------------------------------------------------------- ekstraksi teks
def _clean(text: str) -> str:
    text = re.sub(r"-\n(?=[a-z])", "", text)  # gabung kata yang terpotong di akhir baris
    text = re.sub(r"\s+", " ", text)
    # buang daftar pustaka di akhir (sering mendominasi dan tidak berguna sebagai kutipan)
    m = list(re.finditer(r"\b(?:References|REFERENCES|Bibliography|Daftar Pustaka|DAFTAR PUSTAKA)\b", text))
    if m and m[-1].start() > len(text) * 0.5:
        text = text[: m[-1].start()]
    return text.strip()


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[:MAX_PDF_PAGES]
    return _clean(" ".join((p.extract_text() or "") for p in pages))


def fetch_fulltext(
    ref: ReferenceItem,
    cache_dir: Path,
    get: Callable[..., requests.Response] = _default_get,
) -> Optional[str]:
    """Ambil teks lengkap sebuah referensi (cache disk). None bila tidak tersedia."""
    if not ref.link:
        return None
    cache = cache_dir / (hashlib.sha1(ref.link.encode()).hexdigest() + ".txt")
    if cache.exists():
        return cache.read_text(encoding="utf-8") or None

    def get_json(url: str) -> Optional[dict]:
        try:
            r = get(url)
            return r.json() if r.ok else None
        except Exception:
            return None

    text = None
    try:
        target = resolve_pdf_url(ref.link, get_json)
        if target:
            kind, url = target
            r = get(url)
            if r.ok and len(r.content) <= MAX_PDF_BYTES:
                if kind == "pdf" and r.content[:5] == b"%PDF-":
                    text = extract_pdf_text(r.content)
                elif kind == "html":
                    import trafilatura

                    text = _clean(trafilatura.extract(r.text) or "")
    except Exception:
        text = None

    text = text if text and len(text) > 500 else None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(text or "", encoding="utf-8")
    except OSError:
        pass
    return text


# --------------------------------------------------------------------------- BM25
def _tokens(s: str) -> List[str]:
    return [w for w in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", s.lower()) if w not in _STOP]


def chunk_text(text: str, size: int = CHUNK_CHARS) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > size:
            chunks.append(cur)
            cur = ""
        cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) > 80]


def bm25_rank(chunks: List[str], query: str, k1: float = 1.5, b: float = 0.75) -> List[int]:
    """Indeks chunk, terbaik dulu (chunk tanpa kata cocok dibuang)."""
    docs = [Counter(_tokens(c)) for c in chunks]
    if not docs:
        return []
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1
    df = Counter(t for d in docs for t in d)
    n = len(docs)
    q = set(_tokens(query))
    scores = []
    for i, d in enumerate(docs):
        ln = sum(d.values())
        s = 0.0
        for t in q:
            if t in d:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * d[t] * (k1 + 1) / (d[t] + k1 * (1 - b + b * ln / avg))
        scores.append((s, i))
    return [i for s, i in sorted(scores, reverse=True) if s > 0]


# --------------------------------------------------------------------------- orkestrasi
@dataclass
class FullTextStore:
    """Menyimpan teks referensi + melacak chunk yang sudah dipakai agar antar sub-bab tidak berulang."""

    texts: Dict[int, str] = field(default_factory=dict)  # indeks daftar_pustaka -> teks
    _chunks: Dict[int, List[str]] = field(default_factory=dict)
    _used: Set[Tuple[int, int]] = field(default_factory=set)

    def load(self, refs: List[ReferenceItem], cache_dir: Path, get=_default_get, workers: int = 4) -> int:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda r: fetch_fulltext(r, cache_dir, get), refs))
        for i, text in enumerate(results):
            if text:
                self.texts[i] = text
                self._chunks[i] = chunk_text(text)
        return len(self.texts)

    def passages(self, ref_idx: int, ref: ReferenceItem, topic: str, budget_chars: int) -> List[str]:
        """Kutipan paling relevan untuk satu referensi, urut sesuai posisi di paper."""
        chunks = self._chunks.get(ref_idx)
        if not chunks or budget_chars <= 0:
            return []
        query = f"{topic} {ref.title} {ref.excerpt or ''}"
        picked, used_chars = [], 0
        for i in bm25_rank(chunks, query):
            if (ref_idx, i) in self._used:
                continue
            if used_chars + len(chunks[i]) > budget_chars:
                continue
            picked.append(i)
            used_chars += len(chunks[i])
        self._used.update((ref_idx, i) for i in picked)
        return [chunks[i] for i in sorted(picked)]
