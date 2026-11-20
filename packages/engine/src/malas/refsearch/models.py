"""Struktur data pencarian referensi deterministik."""
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class SectionQuery:
    """Rencana pencarian untuk satu sub-bab."""

    section: str  # judul sub-bab apa adanya, mis. "2.1 Landasan Teori"
    q_en: str = ""  # query bahasa Inggris (boleh kosong)
    q_id: str = ""  # query bahasa Indonesia (boleh kosong)
    bidang: str = "umum"  # medis | teknik | sains | sosial | hukum | agama | ekonomi | humaniora | pendidikan | umum
    indo: bool = False  # topik spesifik Indonesia -> sertakan sumber & bahasa Indonesia

    def queries(self) -> List[tuple]:
        out, seen = [], set()
        for lang, q in (("en", self.q_en), ("id", self.q_id)):
            q = " ".join(q.split())
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append((lang, q))
        return out


@dataclass
class Candidate:
    """Satu hasil dari satu sumber. Semua field berasal dari respons API, bukan dari LLM."""

    source: str
    source_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    venue: Optional[str] = None
    volume: Optional[str] = None  # metadata bibliografis untuk APA 7 (opsional; tidak semua sumber memberi)
    issue: Optional[str] = None
    pages: Optional[str] = None  # "36–52" (en dash) atau satu halaman
    language: Optional[str] = None
    cited_by: int = 0
    kind: str = "article"  # article | book | encyclopedia
    oa_pdf_url: Optional[str] = None
    ranks: List[int] = field(default_factory=list)  # posisi pada tiap (sumber, query); dasar RRF
    sources: Set[str] = field(default_factory=set)
    sections: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.sources.add(self.source)
