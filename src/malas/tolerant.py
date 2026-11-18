"""Parser toleran untuk keluaran LLM -> model pydantic, tanpa panggilan LLM tambahan.

Latar belakang: bila keluaran LLM bukan JSON yang pas dengan skema, CrewAI meminta LLM
"memformat ulang" sampai 3 kali (boros token), dan pada jalur tertentu CrewAI sendiri crash
dengan "Agent must be provided if converter_cls is not specified". `TolerantConverter` dipasang
sebagai `converter_cls` pada Task agar keluaran dirapikan secara lokal:

  1. cari JSON di dalam teks (pagar ```json, prosa di sekitarnya),
  2. samakan bentuknya (nama kunci alternatif, string vs list, tahun sebagai teks, ...),
  3. bila bukan JSON sama sekali, ubah teks apa adanya menjadi paragraf/daftar.
"""
import json
import re
from typing import Any, List, Optional

from crewai.utilities.converter import Converter, ConverterError

from malas.crews.models.TaskOutput import (
    ContentItem, ContentList, ContentText, KataPengantar, Outline, ReferenceItem, References,
    SimpleSubbab, SubBab,
)

_FENCE = re.compile(r"```[a-zA-Z]*\s*(.*?)```", re.S)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-zA-Z][.)])\s+")
_HEADING = re.compile(r"^\s*#{1,6}\s+")
_MAX_STARTS = 300


class ParseError(ValueError):
    pass


# --------------------------------------------------------------------------- util
def extract_json(text: str) -> Optional[Any]:
    """JSON (dict/list) pertama di dalam teks, atau None."""
    dec = json.JSONDecoder(strict=False)
    for cand in [m.group(1) for m in _FENCE.finditer(text)] + [text]:
        tried = 0
        for i, ch in enumerate(cand):
            if ch not in "{[":
                continue
            tried += 1
            if tried > _MAX_STARTS:
                break
            try:
                obj, _ = dec.raw_decode(cand[i:])
            except ValueError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
    return None


def _s(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        return " ".join(_s(i) for i in x if _s(i))
    if isinstance(x, dict):
        return " ".join(_s(v) for v in x.values() if _s(v))
    return str(x).strip()


def _clean_md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", s)
    return s.strip()


def _first(d: dict, keys) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, "", []):
            return d[k]
    return None


# --------------------------------------------------------------------------- SubBab
def _items_from_prose(text: str) -> List[ContentItem]:
    text = re.sub(r"^\s*final answer\s*:\s*", "", text.strip(), flags=re.I)
    text = _FENCE.sub(lambda m: m.group(1), text)
    out: List[ContentItem] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip() and not _HEADING.match(l)]
        if not lines:
            continue
        bullets = [bool(_BULLET.match(l)) for l in lines]
        if all(bullets):
            out.append(ContentList(items=[_clean_md(_BULLET.sub("", l)) for l in lines]))
        elif len(lines) > 1 and not bullets[0] and all(bullets[1:]) and lines[0].rstrip().endswith(":"):
            out.append(ContentList(title_items=_clean_md(lines[0]), items=[_clean_md(_BULLET.sub("", l)) for l in lines[1:]]))
        else:
            out.append(ContentText(isi=_clean_md(" ".join(l.strip() for l in lines))))
    return out


def _content_from(item: Any) -> List[ContentItem]:
    if item is None:
        return []
    if isinstance(item, str):
        return _items_from_prose(item) if item.strip() else []
    if isinstance(item, list):
        return [c for i in item for c in _content_from(i)]
    if isinstance(item, dict):
        items = _first(item, ("items", "list", "poin", "daftar", "butir"))
        if str(item.get("type", "")).lower() == "list" or isinstance(items, list):
            rows = [_clean_md(_s(x)) for x in (items if isinstance(items, list) else [items]) if _s(x)]
            if rows:
                title = _first(item, ("title_items", "title", "judul", "heading"))
                return [ContentList(title_items=_s(title) or None, items=rows)]
            return []
        body = _first(item, ("isi", "text", "teks", "paragraph", "paragraf", "content", "konten", "body", "deskripsi"))
        if isinstance(body, (list, dict)):
            return _content_from(body)
        return [ContentText(isi=_clean_md(_s(body)))] if _s(body) else []
    return []


def parse_subbab(text: str) -> SubBab:
    obj = extract_json(text)
    judul = ""
    if isinstance(obj, dict):
        judul = _s(obj.get("judul") or obj.get("title"))
        inner = obj.get("content") if "content" in obj else obj.get("konten") if "konten" in obj else obj
        contents = _content_from(inner)
    elif isinstance(obj, list):
        contents = _content_from(obj)
    else:
        contents = _items_from_prose(text)
    if not contents:
        raise ParseError("Keluaran sub-bab kosong")
    return SubBab(judul=judul, content=contents)


# --------------------------------------------------------------------------- KataPengantar
def parse_kata_pengantar(text: str) -> KataPengantar:
    obj = extract_json(text)
    isi = ""
    if isinstance(obj, dict):
        v = _first(obj, ("isi", "kata_pengantar", "text", "teks", "content"))
        isi = "\n".join(_s(x) for x in v) if isinstance(v, list) else _s(v)
    if not isi:
        body = _FENCE.sub(lambda m: m.group(1), text)
        lines = [l.rstrip() for l in body.splitlines() if not _HEADING.match(l)]
        lines = [l for l in lines if l.strip().lower().strip("*# ") != "kata pengantar"]
        isi = "\n".join(_clean_md(l) for l in lines).strip()
    if not isi:
        raise ParseError("Kata pengantar kosong")
    return KataPengantar(isi=isi)


# --------------------------------------------------------------------------- References
def _authors(v: Any) -> List[str]:
    if isinstance(v, list):
        return [_s(a) for a in v if _s(a)]
    s = _s(v)
    if not s:
        return []
    parts = [p.strip() for p in re.split(r";|\sand\s|\sdan\s|\s&\s", s) if p.strip()]
    return parts or [s]


def _year(v: Any) -> Optional[int]:
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", _s(v))
    return int(m.group(1)) if m else None


def parse_references(text: str) -> References:
    obj = extract_json(text)
    rows = None
    if isinstance(obj, list):
        rows = obj
    elif isinstance(obj, dict):
        rows = obj.get("references") or obj.get("referensi") or next((v for v in obj.values() if isinstance(v, list)), None)
    if not rows:
        raise ParseError("Daftar referensi tidak ditemukan")
    refs: List[ReferenceItem] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = _s(_first(r, ("title", "judul", "name")))
        year = _year(_first(r, ("year", "tahun", "date", "published")))
        if not title or year is None:
            continue  # tanpa judul/tahun tidak bisa disitasi dengan benar; lebih baik dibuang daripada mengarang
        link = _s(_first(r, ("link", "url", "pdf", "href")))
        doi = _s(r.get("doi"))
        if not link and doi:
            link = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        refs.append(ReferenceItem(
            title=title, authors=_authors(_first(r, ("authors", "author", "penulis"))), year=year,
            link=link or None, excerpt=_s(_first(r, ("excerpt", "abstract", "ringkasan", "summary"))) or None,
        ))
    if not refs:
        raise ParseError("Tidak ada referensi valid")
    return References(references=refs)


# --------------------------------------------------------------------------- Outline
def parse_outline(text: str) -> Outline:
    obj = extract_json(text)
    mapping = None
    if isinstance(obj, dict):
        mapping = obj.get("subbabs") or obj.get("outline") or obj.get("bab") or obj
    result = {}
    if isinstance(mapping, dict):
        for bab, val in mapping.items():
            secs = val.get("sections") or val.get("subbab") or val.get("sub_bab") if isinstance(val, dict) else val
            if isinstance(secs, list):
                rows = [_s(x) for x in secs if _s(x)]
                if rows:
                    result[str(bab)] = SimpleSubbab(sections=rows)
    if not result:  # prosa: "Bab 1: ..." diikuti baris "1.1 ..."
        cur = None
        for line in text.splitlines():
            plain = re.sub(r"^\s*[-*]\s+", "", _clean_md(re.sub(r"^\s*#+\s*", "", line)))
            if re.match(r"^bab\s+\w+", plain, re.I):
                cur = plain
                result[cur] = SimpleSubbab(sections=[])
            elif cur and re.match(r"^\d+\.\d+\s+\S", plain):
                result[cur].sections.append(plain)
        result = {k: v for k, v in result.items() if v.sections}
    if not result:
        raise ParseError("Outline tidak ditemukan")
    return Outline(subbabs=result)


_PARSERS = {
    SubBab: parse_subbab, KataPengantar: parse_kata_pengantar, References: parse_references, Outline: parse_outline,
}


class TolerantConverter(Converter):
    """Pengganti converter CrewAI: merapikan keluaran secara lokal, tanpa LLM."""

    def to_pydantic(self, current_attempt: int = 1):  # noqa: ARG002
        parse = _PARSERS.get(self.model)
        if parse is None:
            return super().to_pydantic(current_attempt)
        try:
            return parse(self.text)
        except Exception as e:  # noqa: BLE001
            # DIKEMBALIKAN (bukan di-raise): CrewAI lalu memakai teks mentah dan pemanggil bisa menangani.
            return ConverterError(f"Keluaran tidak sesuai skema {self.model.__name__}: {e}")

    def to_json(self, current_attempt: int = 1):  # noqa: ARG002
        out = self.to_pydantic()
        return out if isinstance(out, ConverterError) else out.model_dump()
