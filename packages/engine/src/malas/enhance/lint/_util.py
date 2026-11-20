"""Utilitas teks bersama aturan lint (murni kode, tanpa LLM/jaringan).

Isi: iterasi sub-bab/paragraf, pemecah kalimat sederhana (sadar singkatan "dkk.", "et al.", inisial), token bermakna
(tanpa stopword Indonesia), stemmer kasar, pencarian sub-bab menurut judul, pemetaan sitasi -> referensi, dan
`ref_key` (kunci kartu bukti).
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

from malas.citations import _ref_keys, extract_citations
from malas.crews.models.TaskOutput import ContentList, ContentTable, ContentText, Makalah, ReferenceItem, SubBab
from malas.enhance.models import EvidenceCard

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}

# Stopword Indonesia (fungsi + kata umum makalah). Kata topik TIDAK boleh masuk sini.
STOPWORDS: set[str] = {"ada", "adalah", "adanya", "agar", "akan", "akhirnya", "aku", "amat", "antara", "antar", "apa", "apabila", "apakah", "atas", "atau", "bagai", "bagaimana", "bagi", "bahkan", "bahwa", "baik", "banyak", "baru", "beberapa", "begitu", "belum", "benar", "berada", "berbagai", "beri", "berikut", "bersama", "besar", "bila", "bisa", "boleh", "bukan", "bukanlah", "cara", "cukup", "dalam", "dan", "dapat", "dari", "daripada", "demikian", "dengan", "di", "dia", "diri", "dua", "hal", "hanya", "harus", "hingga", "ia", "ialah", "ini", "itu", "jadi", "jika", "juga", "justru", "kadang", "kali", "kami", "kamu", "karena", "ke", "kecil", "kedua", "keempat", "kelima", "ketiga", "kembali", "kemudian", "kepada", "kita", "lagi", "lain", "lainnya", "lalu", "lebih", "maka", "mana", "masih", "masing", "melalui", "membuat", "menjadi", "menurut", "merupakan", "mereka", "meski", "meskipun", "misalnya", "mungkin", "namun", "oleh", "pada", "para", "pasti", "pernah", "pertama", "perlu", "saat", "saja", "salah", "sama", "sambil", "sangat", "satu", "saya", "sebab", "sebagai", "sebagaimana", "sebelum", "sebelumnya", "sebuah", "secara", "sedang", "sedangkan", "sehingga", "sejak", "sekali", "selain", "selalu", "seluruh", "semua", "semakin", "sementara", "sendiri", "seperti", "serta", "sesuai", "setelah", "setiap", "suatu", "sudah", "supaya", "tak", "tanpa", "tapi", "telah", "tentang", "terhadap", "terutama", "tetapi", "tiap", "tidak", "tiga", "turut", "untuk", "utama", "walau", "walaupun", "yaitu", "yakni", "yang", "the", "of", "and", "in", "to", "for", "on", "with", "by", "is", "are", "a", "an", "as", "at", "from", "that", "this", "be", "or", "bab", "subbab", "sub", "makalah", "kajian", "penulis", "uraian", "diuraikan", "dibahas", "pembahasan", "berdasarkan", "disimpulkan", "kesimpulan"}

_ABBR = re.compile(r"\b(?:dkk|et al|hlm|dll|dsb|dst|no|vol|dr|prof|mis|yth|[A-Z])\.$", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z\"“(\[0-9])")
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def fold(s: str) -> str:
    """Huruf kecil tanpa diakritik (untuk pencocokan)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def bab_order(key: str) -> int:
    k = (key or "").strip().upper()
    if k in _ROMAN:
        return _ROMAN[k]
    return int(k) if k.isdigit() else 99


def iter_subbab(makalah: Makalah) -> Iterator[tuple[str, int, SubBab]]:
    """(kunci bab, indeks sub-bab, sub-bab) berurutan menurut nomor bab."""
    for key in sorted(makalah.bab, key=bab_order):
        for i, sub in enumerate(makalah.bab[key].subbab):
            yield key, i, sub


def item_texts(sub: SubBab) -> list[tuple[int, str]]:
    """(indeks konten, teks) per paragraf; butir daftar dikembalikan per butir (indeks konten yang sama)."""
    out: list[tuple[int, str]] = []
    for i, c in enumerate(sub.content):
        if isinstance(c, ContentText):
            out.append((i, c.isi))
        elif isinstance(c, ContentList):
            if c.title_items:
                out.append((i, c.title_items))
            out.extend((i, it) for it in c.items)
        elif isinstance(c, ContentTable):
            out.extend((i, " | ".join(r)) for r in c.rows)
    return out


def paragraphs(sub: SubBab) -> list[tuple[int, str]]:
    """(indeks konten, teks) hanya untuk paragraf naratif (ContentText)."""
    return [(i, c.isi) for i, c in enumerate(sub.content) if isinstance(c, ContentText) and c.isi.strip()]


def sub_text(sub: SubBab) -> str:
    return "\n".join(t for _, t in item_texts(sub))


def sentences(text: str) -> list[str]:
    """Pecah kalimat; tidak memotong setelah singkatan ("dkk.", "et al.", inisial "M.")."""
    text = " ".join((text or "").split())
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    out: list[str] = []
    for p in parts:
        if out and _ABBR.search(out[-1]):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return [s.strip() for s in out if s.strip()]


def words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text or "")]


_PREFIX = re.compile(r"^(?:meng|meny|mem|men|me|peng|peny|pem|pen|pe|ber|be|ter|di|ke|se)(?=\w{4,})")
_SUFFIX = re.compile(r"(?:kan|an|i|nya|lah|kah)$")


def stem(word: str) -> str:
    """Stemmer KASAR (bukan Sastrawi): buang satu awalan + satu akhiran, ambil 5 huruf pertama sebagai kunci."""
    w = fold(word)
    if len(w) > 6:
        w2 = _SUFFIX.sub("", w)
        w = w2 if len(w2) >= 4 else w
    if len(w) > 6:
        w2 = _PREFIX.sub("", w)
        w = w2 if len(w2) >= 4 else w
    return w[:5]


def _unredup(w: str) -> str:
    """Kata ulang "bentuk-bentuk" / "faktor-faktor" -> "bentuk" / "faktor"."""
    parts = w.split("-")
    return parts[0] if len(parts) == 2 and parts[0] == parts[1] else w


def content_tokens(text: str) -> list[str]:
    """Token bermakna (>=3 huruf, bukan stopword), kata ulang disederhanakan, sudah di-stem."""
    return [stem(w) for w in map(_unredup, words(text)) if len(w) >= 3 and w not in STOPWORDS]


def idf_table(docs: list[list[str]]) -> dict[str, float]:
    n = max(1, len(docs))
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}


def title_core(judul: str) -> str:
    """Judul tanpa nomor depan ("2.1 2.1 Konsep" -> "Konsep")."""
    return re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+)+", "", judul or "").strip()


def find_subbabs(makalah: Makalah, *keywords: str, bab: str | None = None) -> list[tuple[str, int, SubBab]]:
    kws = [fold(k) for k in keywords]
    out = []
    for key, i, sub in iter_subbab(makalah):
        if bab and key != bab:
            continue
        t = fold(title_core(sub.judul))
        if any(k in t for k in kws):
            out.append((key, i, sub))
    return out


def kesimpulan_subbab(makalah: Makalah) -> tuple[str, int, SubBab] | None:
    hit = find_subbabs(makalah, "kesimpulan", "simpulan")
    if hit:
        return hit[0]
    keys = sorted(makalah.bab, key=bab_order)
    if keys and bab_order(keys[-1]) >= 3 and makalah.bab[keys[-1]].subbab:
        return keys[-1], 0, makalah.bab[keys[-1]].subbab[0]
    return None


_QWORDS = re.compile(r"\b(?:apa|apakah|bagaimana|bagaimanakah|mengapa|kenapa|sejauh\s+mana|seberapa|siapa|kapan|"
                     r"di\s*mana|manakah)\b", re.IGNORECASE)


def is_question(text: str) -> bool:
    return "?" in (text or "") or bool(_QWORDS.search(text or ""))


_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-zA-Z][.)])\s+")


def list_items(sub: SubBab) -> list[tuple[int, str]]:
    """Butir daftar sub-bab (RM/Tujuan): butir ContentList, atau baris teks (tanpa marker) bila hanya teks."""
    items = [(i, it) for i, c in enumerate(sub.content) if isinstance(c, ContentList) for it in c.items if it.strip()]
    if items:
        return items
    out = []
    for i, c in enumerate(sub.content):
        if isinstance(c, ContentText):
            out.extend((i, _MARKER.sub("", ln, count=1).strip()) for ln in c.isi.splitlines() if ln.strip())
    return out


def ref_key(ref: ReferenceItem) -> str:
    """Kunci kartu bukti: sama dengan `evidence.ref_key_of` ("doi:<doi>" atau "t:<hash judul+tahun>")."""
    from malas.enhance.evidence import ref_key_of

    return ref_key_of(ref)


def card_for(makalah: Makalah, idx: int) -> EvidenceCard | None:
    if not makalah.evidence or idx >= len(makalah.daftar_pustaka):
        return None
    ref = makalah.daftar_pustaka[idx]
    for k in (ref_key(ref), ref.doi or "", ref.title):
        if k and k in makalah.evidence:
            return makalah.evidence[k]
    return None


@dataclass
class RefIndex:
    """Peta (nama keluarga ternormalisasi, tahun) -> indeks daftar pustaka."""

    keys: list[set[tuple]]

    @classmethod
    def of(cls, makalah: Makalah) -> RefIndex:
        return cls([_ref_keys(r) for r in makalah.daftar_pustaka])

    def cited(self, text: str) -> list[tuple[str, list[int]]]:
        """[(sitasi mentah, [indeks referensi yang cocok])]."""
        out = []
        for c in extract_citations(text):
            out.append((c.raw, [i for i, k in enumerate(self.keys) if (c.surname, c.year) in k]))
        return out

    def cited_refs(self, text: str) -> set[int]:
        return {i for _, hits in self.cited(text) for i in hits}


_HAS_CITE = re.compile(r"\((?:[^()]*?\b(?:1[89]|20)\d{2}[a-z]?)[^()]*\)|\b[A-ZÀ-Ý][\w'’\-]*\.?(?:\s+(?:dkk\.|et al\.)|"
                       r"\s+(?:dan|&)\s+[A-ZÀ-Ý][\w'’\-]+)?\s*\((?:1[89]|20)\d{2}[a-z]?\)")


def has_citation(text: str) -> bool:
    """Ada sitasi bergaya APA (dikenali ATAU mirip) di teks."""
    return bool(_HAS_CITE.search(text or ""))


def clip(s: str, n: int = 200) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"
