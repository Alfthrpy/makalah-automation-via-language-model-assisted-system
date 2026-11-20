"""Verifikasi sitasi in-text terhadap daftar pustaka (tanpa LLM, murni kode).

Format sitasi yang dikenali (APA 7):
  (Smith, 2024)  (Smith & Jones, 2024)  (Smith et al., 2024)  (Smith dkk., 2024)
  (Smith, 2024; Lee, 2023)   dan bentuk naratif:  Smith (2024)  Smith dan Jones (2024)
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from malas.crews.models.TaskOutput import (
    ContentItem, ContentList, ContentTable, ContentText, Makalah, ReferenceItem,
)
from malas.names import family_of, is_institution  # noqa: F401  (is_institution diekspor ulang untuk docx_converter)

_NAMA = r"[A-ZÀ-Ý][\w'’\-]+"
# (Nama[, Nama2 | & Nama2 | dan Nama2 | et al. | dkk.], 2024[a])  -- boleh beberapa dipisah ';'
_PAREN = re.compile(r"\(([^()]*?\b(?:1[89]|20)\d{2}[a-z]?[^()]*?)\)")
_ITEM = re.compile(
    rf"^\s*(?P<nama>{_NAMA}(?:[^,()]*?))\s*,\s*(?P<tahun>(?:1[89]|20)\d{{2}})[a-z]?\s*(?:[,:]\s*(?:hlm|p|pp)\.?\s*[\d\-–]+)?\s*$"
)
_NARASI = re.compile(
    rf"(?P<nama>{_NAMA}(?:\s+(?:dan|&|and)\s+{_NAMA}|\s+(?:et al\.|dkk\.))?)\s*\((?P<tahun>(?:1[89]|20)\d{{2}})[a-z]?\)"
)

# Sitasi-MIRIP yang gagal diurai (mis. "(M dkk., 2026)": nama 1 huruf) tidak boleh hilang tanpa jejak:
# tanpa ini verifier "bersih" padahal rusak dan referensinya terbuang sebagai "tak dikutip".
_SUSPECT_ITEM = re.compile(r"^\s*[A-ZÀ-Ý][^,()]{0,60}?\s*,\s*(?:1[89]|20)\d{2}[a-z]?\b")
_SUSPECT_NARASI = re.compile(r"(?<![\w])[A-ZÀ-Ý]\.?\s+(?:dkk\.|et al\.)\s*\(\s*(?:1[89]|20)\d{2}[a-z]?\s*\)")
_BUKAN_SITASI = re.compile(r"^\s*(?:gambar|gbr|tabel|bab|lihat|fig(?:ure)?|table|bagian|halaman|hlm|pasal|ayat|surah|qs|hr)\b", re.I)


def find_suspects(text: str) -> List[str]:
    """Kurung/naratif bergaya sitasi (Nama..., tahun) yang TIDAK dikenali `extract_citations`."""
    out: List[str] = []
    for m in _PAREN.finditer(text):
        for part in m.group(1).split(";"):
            if _ITEM.match(part) or _BUKAN_SITASI.match(part):
                continue
            if _SUSPECT_ITEM.match(part):
                out.append(f"({part.strip()})")
    out.extend(m.group(0) for m in _SUSPECT_NARASI.finditer(text))
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def _surname(author: str) -> str:
    """'Raseena, P. M.' / 'John Smith' -> 'raseena' / 'smith' (kata terakhir nama keluarga, ternormalisasi)."""
    family = family_of(author).split()
    return _norm(family[-1]) if family else ""


@dataclass(frozen=True)
class Citation:
    raw: str
    surname: str  # nama belakang penulis pertama (ternormalisasi)
    year: int


def extract_citations(text: str) -> List[Citation]:
    found: List[Citation] = []
    for m in _PAREN.finditer(text):
        for part in m.group(1).split(";"):
            it = _ITEM.match(part)
            if it:
                first = re.split(r"\s*(?:&|\bdan\b|\band\b|\bet al\.|\bdkk\.)\s*|,\s*", it["nama"].strip())[0]
                found.append(Citation(f"({part.strip()})", _norm(first.split()[-1]), int(it["tahun"])))
    for m in _NARASI.finditer(text):
        first = re.split(r"\s+(?:dan|&|and|et al\.|dkk\.)", m["nama"])[0]
        found.append(Citation(f"{m.group(0)}", _norm(first.split()[-1]), int(m["tahun"])))
    return found


def citation_label(ref: ReferenceItem) -> str:
    """Bentuk sitasi in-text yang benar untuk sebuah referensi, mis. '(Smith & Jones, 2024)'."""
    names = [_surname_display(a) for a in ref.authors if a.strip()]
    if not names:
        return f"({ref.title.split(':')[0].strip()}, {ref.year})"
    if len(names) == 1:
        who = names[0]
    elif len(names) == 2:
        who = f"{names[0]} & {names[1]}"
    else:
        who = f"{names[0]} dkk."
    return f"({who}, {ref.year})"


def _surname_display(author: str) -> str:
    author = author.strip()
    if is_institution(author) and "," not in author:
        return author
    return family_of(author)


def _ref_keys(ref: ReferenceItem) -> Set[tuple]:
    keys = {(_surname(a), ref.year) for a in ref.authors if a.strip()}
    for a in ref.authors:
        if a.strip() and is_institution(a):
            # in-text "(Kementerian Pendidikan dan Kebudayaan, 2023)" dipotong di "dan" oleh extract_citations
            seg = re.split(r"\s+(?:dan|&|and)\s+|\s+(?:et al\.|dkk\.)", a.strip())[0].split()
            if seg:
                keys.add((_norm(seg[-1]), ref.year))
    if not ref.authors:  # sumber tanpa penulis: sitasi memakai judul
        keys.add((_norm(ref.title.split(":")[0].split()[0] if ref.title.split() else ""), ref.year))
    return keys


def content_text(contents: List[ContentItem]) -> str:
    """Ratakan konten sub-bab (teks + list) jadi satu string."""
    parts: List[str] = []
    for item in contents:
        if isinstance(item, ContentText):
            parts.append(item.isi)
        elif isinstance(item, ContentList):
            if item.title_items:
                parts.append(item.title_items)
            parts.extend(f"- {li}" for li in item.items)
        elif isinstance(item, ContentTable):
            if item.caption:
                parts.append(item.caption)
            if item.header:
                parts.append(" | ".join(item.header))
            parts.extend(" | ".join(row) for row in item.rows)
    return "\n".join(parts)


@dataclass
class CitationReport:
    # judul sub-bab -> sitasi yang tidak ada di daftar pustaka
    invalid: Dict[str, List[str]] = field(default_factory=dict)
    used_refs: Set[int] = field(default_factory=set)  # indeks daftar_pustaka yang dikutip
    unused_refs: List[int] = field(default_factory=list)
    total_citations: int = 0
    # judul sub-bab -> sitasi-mirip yang tak bisa diurai (tak diketahui sah/tidaknya): wajib diperiksa
    suspect: Dict[str, List[str]] = field(default_factory=dict)
    pruned_titles: List[str] = field(default_factory=list)  # diisi prune_unused_references

    @property
    def ok(self) -> bool:
        return not self.invalid and not self.suspect

    @property
    def problems(self) -> Dict[str, List[str]]:
        """Gabungan sitasi tidak sah + mencurigakan per sub-bab (bahan perbaikan)."""
        merged: Dict[str, List[str]] = {k: list(v) for k, v in self.invalid.items()}
        for k, v in self.suspect.items():
            merged.setdefault(k, []).extend(x for x in v if x not in merged.get(k, []))
        return merged


def check_citations(makalah: Makalah, only: Optional[Set[str]] = None) -> CitationReport:
    keys = [_ref_keys(r) for r in makalah.daftar_pustaka]
    report = CitationReport()
    for bab in makalah.bab.values():
        for sub in bab.subbab:
            if only is not None and sub.judul not in only:
                continue
            teks = content_text(sub.content)
            suspects = find_suspects(teks)
            if suspects:
                report.suspect[sub.judul] = suspects
            for c in extract_citations(teks):
                report.total_citations += 1
                hit = [i for i, k in enumerate(keys) if (c.surname, c.year) in k]
                if hit:
                    report.used_refs.update(hit)
                else:
                    report.invalid.setdefault(sub.judul, []).append(c.raw)
    report.unused_refs = [i for i in range(len(keys)) if i not in report.used_refs]
    return report


def prune_unused_references(makalah: Makalah, report: CitationReport) -> int:
    """Buang referensi yang tidak pernah dikutip (aturan APA: pustaka = yang dikutip).

    Aman: tidak melakukan apa-apa bila (a) tidak satu pun sitasi cocok (mis. LLM tidak memakai format APA),
    atau (b) ada sitasi mencurigakan yang tak bisa diurai (`report.suspect`): referensi "tak terpakai" bisa
    jadi justru sumbernya. Judul yang dibuang dicatat di `report.pruned_titles`.
    """
    report.pruned_titles = []
    if not report.used_refs or report.suspect:
        return 0
    before = len(makalah.daftar_pustaka)
    report.pruned_titles = [r.title for i, r in enumerate(makalah.daftar_pustaka) if i not in report.used_refs]
    makalah.daftar_pustaka = [r for i, r in enumerate(makalah.daftar_pustaka) if i in report.used_refs]
    return before - len(makalah.daftar_pustaka)
