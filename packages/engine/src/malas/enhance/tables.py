"""Tabel sintesis studi dirakit KODE dari kartu bukti (tanpa token penulis). docs/enhancing-engine.md §7 S13."""
import re

from malas.citations import citation_label
from malas.crews.models.TaskOutput import ContentTable, Makalah
from malas.enhance.evidence import DESIGN_LABEL, OUTCOME_LABEL, ref_key_of

MIN_CARDS = 3
MAX_ROWS = 8
CAPTION = "Tabel 1. Sintesis studi yang dikaji"
_HEADER = ["Penulis (tahun)", "Desain", "Sampel", "Hasil utama", "Keterbatasan"]
_TARGET = re.compile(r"\b(studi|penelitian|temuan|dampak|hasil|analisis)\b", re.IGNORECASE)


def _cell(s, n: int = 120) -> str:
    s = " ".join(str(s or "").split())
    s = s.replace("|", "/")
    return (s[: n - 1].rstrip() + "…") if len(s) > n else (s or "-")


def build_synthesis_table(state: Makalah) -> ContentTable | None:
    rows = []
    for ref in state.daftar_pustaka:
        card = state.evidence.get(ref_key_of(ref))
        if card is None or (card.design == "tak_diketahui" and not card.key_result):
            continue
        sample = " ".join(x for x in (f"n = {card.n}" if card.n else "", card.population) if x)
        rows.append([citation_label(ref).strip("()"), DESIGN_LABEL.get(card.design, card.design),
                     sample or "-", card.key_result or OUTCOME_LABEL.get(card.outcome, "-"), card.limitations or "-"])
    if len(rows) < MIN_CARDS:
        return None
    return ContentTable(caption=CAPTION, header=list(_HEADER), rows=[[_cell(c) for c in r] for r in rows[:MAX_ROWS]])


def attach_synthesis_table(state: Makalah) -> bool:
    """Sisipkan tabel di akhir sub-bab Bab II yang relevan (bukan ganda). True bila tersisip."""
    bab2 = state.bab.get("II")
    if not bab2 or not bab2.subbab or any(isinstance(c, ContentTable) for sb in bab2.subbab for c in sb.content):
        return False
    table = build_synthesis_table(state)
    if table is None:
        return False
    target = next((sb for sb in reversed(bab2.subbab) if _TARGET.search(sb.judul) and sb.content), None) \
        or next((sb for sb in reversed(bab2.subbab) if sb.content), None)
    if target is None:
        return False
    target.content.append(table)
    return True
