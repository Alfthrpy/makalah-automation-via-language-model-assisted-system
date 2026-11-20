"""Rerank opsional oleh LLM murah: LLM hanya MEMILIH ID dari kandidat, tidak pernah menulis referensi.

Aman terhadap kegagalan: JSON rusak / ID asing / exception -> kembali ke urutan deterministik.
"""
import json
import re
from typing import Callable, List, Optional

from malas.refsearch.models import Candidate, SectionQuery

MAX_CANDIDATES = 6  # kandidat teratas yang diperlihatkan ke LLM
ABSTRACT_CHARS = 260


def build_prompt(sq: SectionQuery, judul: str, cands: List[Candidate], k: int) -> str:
    rows = []
    for i, c in enumerate(cands, 1):
        abst = (c.abstract or "")[:ABSTRACT_CHARS].replace("\n", " ")
        rows.append(f'c{i}. "{c.title}" ({c.year}; {c.venue or "-"}) — {abst}')
    return (
        "Pilih sumber referensi yang PALING relevan dan layak dikutip untuk sub-bab sebuah makalah.\n"
        f'Judul makalah: "{judul}"\nSub-bab: "{sq.section}"\n\nKandidat:\n' + "\n".join(rows) + "\n\n"
        f"Pilih paling banyak {k} kandidat yang benar-benar membahas topik tersebut (bukan sekadar topik mirip). "
        'Jawab HANYA JSON: {"ids": ["c2", "c5"]}. Jika tidak ada yang relevan jawab {"ids": []}.'
    )


def parse_ids(text: str, n: int) -> Optional[List[int]]:
    """Indeks 0-based dari jawaban LLM; ID di luar c1..cN dan duplikat dibuang. None bila tidak bisa dibaca."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(0)).get("ids")
    except (ValueError, AttributeError):
        return None
    if not isinstance(raw, list):
        return None
    out: List[int] = []
    for x in raw:
        mm = re.fullmatch(r"\s*c?(\d+)\s*", str(x), re.I)
        if mm and 1 <= int(mm.group(1)) <= n and int(mm.group(1)) - 1 not in out:
            out.append(int(mm.group(1)) - 1)
    return out


def rerank(sq: SectionQuery, judul: str, ranked: List[Candidate], k: int,
           call: Callable[[str], str]) -> List[Candidate]:
    """Kembalikan `ranked` dengan pilihan LLM dipindah ke depan. Tidak pernah raise."""
    top = ranked[:MAX_CANDIDATES]
    if len(top) <= k:  # tidak ada yang perlu dipilih
        return ranked
    try:
        ids = parse_ids(call(build_prompt(sq, judul, top, k)), len(top))
    except Exception:  # noqa: BLE001  (LLM boleh gagal)
        return ranked
    if not ids:
        return ranked  # None (tak terbaca) atau [] (LLM menolak semua): percayai urutan deterministik
    chosen = [top[i] for i in ids[:k]]
    return chosen + [c for c in ranked if all(c is not x for x in chosen)]
