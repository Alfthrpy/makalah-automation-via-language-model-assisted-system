"""TRC-001..003: RM terjawab di Kesimpulan, populasi konsisten, Tujuan <-> RM."""
from __future__ import annotations

import re

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import (
    RefIndex,
    bab_order,
    clip,
    content_tokens,
    idf_table,
    item_texts,
    iter_subbab,
    kesimpulan_subbab,
    paragraphs,
    sentences,
)
from malas.enhance.lint.structure import classify_items, rm_subbab, tujuan_subbab
from malas.enhance.models import Finding, Location


def research_questions(makalah: Makalah, ctx: LintContext) -> list[str]:
    """RM dari Blueprint, atau butir sah sub-bab Rumusan Masalah (pengantar/penjelasan dibuang)."""
    if makalah.blueprint and makalah.blueprint.research_questions:
        return [q for q in makalah.blueprint.research_questions if q.strip()]
    found = rm_subbab(makalah)
    if not found:
        return []
    cls = classify_items(found[2], True, int(ctx.th("str002_max_item_chars")))
    items = [t for _, t, r in cls if r == "item"]
    if not items:  # tak ada kalimat tanya: pakai butir non-pengantar
        items = [t for _, t, r in cls if r not in ("intro", "outro")]
    return items


def tujuan_items(makalah: Makalah, ctx: LintContext) -> list[str]:
    found = tujuan_subbab(makalah)
    if not found:
        return []
    cls = classify_items(found[2], False, int(ctx.th("str002_max_item_chars")))
    return [t for _, t, r in cls if r == "item"]


_GENERIC_WORDS = ["bagaimana", "apa", "apakah", "mengapa", "sejauh", "seberapa", "bentuk", "penerapan", "pengaruh", "hubungan", "peran", "menganalisis", "mengetahui", "mendeskripsikan", "menjelaskan", "mengidentifikasi", "merumuskan", "memetakan", "mengkaji"]


def _generic() -> set[str]:
    return {t for w in _GENERIC_WORDS for t in content_tokens(w)}


def _coverage(q_tokens: list[str], para_tokens: set[str], idf: dict[str, float]) -> float:
    uniq = set(q_tokens)
    total = sum(idf.get(t, 1.0) for t in uniq)
    if not total:
        return 1.0
    return sum(idf.get(t, 1.0) for t in uniq if t in para_tokens) / total


def trc001_scores(makalah: Makalah, ctx: LintContext) -> list[tuple[str, float]]:
    """(RM, skor cakupan terbaik di paragraf Kesimpulan) — dipakai aturan & kalibrasi."""
    rqs = research_questions(makalah, ctx)
    concl = kesimpulan_subbab(makalah)
    if not rqs or not concl:
        return []
    docs = [content_tokens(t) for _, _, s in iter_subbab(makalah) for _, t in item_texts(s)]
    idf = idf_table(docs)
    generic = _generic()
    paras = [set(content_tokens(t)) for _, t in item_texts(concl[2])] or [set()]
    whole = set().union(*paras)
    paras.append(whole)  # jawaban bisa tersebar di beberapa paragraf
    out = []
    for q in rqs:
        qt = [t for t in content_tokens(q) if t not in generic]
        best = max(_coverage(qt, p, idf) for p in paras[:-1]) if paras[:-1] else 0.0
        out.append((q, max(best, 0.85 * _coverage(qt, whole, idf))))
    return out


@rule("TRC-001", "Rumusan masalah tanpa jejak leksikal di Kesimpulan", "major", "patch")
def trc001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    th = ctx.th("trc001_min_score")
    concl = kesimpulan_subbab(makalah)
    out = []
    for k, (q, score) in enumerate(trc001_scores(makalah, ctx), 1):
        if score < th:
            out.append(make_finding(
                "TRC-001", Location(bab=concl[0], subbab=concl[2].judul),
                f"RM-{k} hampir tak berjejak di Kesimpulan (skor {score:.2f} < {th:.2f}).", q,
                hint=f"Jawab RM-{k} secara eksplisit di Kesimpulan dengan merujuk sub-bab hasilnya."))
    return out


# --- TRC-002: populasi -------------------------------------------------------------------------------
# kelompok populasi -> (pola kata, tidak peka huruf) + (akronim jenjang, PEKA huruf besar).
# "peserta didik"/"pelajar" generik: tidak dihitung.
POPULATIONS: dict[str, tuple[re.Pattern, re.Pattern | None]] = {
    "mahasiswa": (re.compile(r"\bmahasiswa\b|\bperguruan\s+tinggi\b|\bperkuliahan\b", re.IGNORECASE), None),
    "siswa": (re.compile(r"\b(?:siswa|murid|madrasah)\b|\bsekolah\s+(?:dasar|menengah)\b", re.IGNORECASE),
              re.compile(r"\b(?:MTs|SDIT|SD|SMP|SMA|SMK|MI|MA)\b")),
    "guru": (re.compile(r"\bguru\b", re.IGNORECASE), None),
    "dosen": (re.compile(r"\bdosen\b", re.IGNORECASE), None),
    "santri": (re.compile(r"\bsantri\b|\bpesantren\b", re.IGNORECASE), None),
    "anak usia dini": (re.compile(r"\banak\s+usia\s+dini\b", re.IGNORECASE), re.compile(r"\b(?:PAUD|TK|RA)\b")),
}


def populations(text: str) -> set[str]:
    """Kelompok populasi yang disebut di teks."""
    return {name for name, (words_re, acr_re) in POPULATIONS.items()
            if words_re.search(text or "") or (acr_re is not None and acr_re.search(text or ""))}


def _allowed_populations(makalah: Makalah, ctx: LintContext) -> tuple[set[str], str]:
    scope = " ".join(x for x in (
        makalah.blueprint.scope.subjek if makalah.blueprint else "",
        makalah.blueprint.scope.jenjang if makalah.blueprint else "",
        makalah.subjek, makalah.jenjang) if x)
    if scope.strip():
        return populations(scope), "lingkup makalah"
    cards = " ".join(c.population for c in makalah.evidence.values() if c.population)
    if cards.strip():
        return populations(cards), "populasi kartu bukti"
    if ctx.trc002_body_fallback:
        idx = RefIndex.of(makalah)
        body = []
        for key, _, sub in iter_subbab(makalah):
            if bab_order(key) == 2:
                body.extend(s for _, t in paragraphs(sub) for s in sentences(t) if idx.cited(s))
        pops = populations(" ".join(body))
        if pops:
            return pops, "kalimat bersitasi Bab II"
    return set(), ""


@rule("TRC-002", "Populasi di Kesimpulan tidak sesuai lingkup/bukti (mis. siswa vs mahasiswa)", "major", "patch")
def trc002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    concl = kesimpulan_subbab(makalah)
    if not concl:
        return []
    allowed, basis = _allowed_populations(makalah, ctx)
    if not allowed:
        return []
    out = []
    for p, text in item_texts(concl[2]):
        for sent in sentences(text):
            extra = populations(sent) - allowed
            for pop in sorted(extra):
                out.append(make_finding(
                    "TRC-002", Location(bab=concl[0], subbab=concl[2].judul, paragraph=p),
                    f"Kesimpulan menyebut \"{pop}\", sedangkan {basis} hanya: {', '.join(sorted(allowed))}.", sent,
                    hint="Sesuaikan subjek kesimpulan dengan populasi bukti atau nyatakan sebagai implikasi."))
    return out


@rule("TRC-003", "Jumlah/isi Tujuan tidak sejajar dengan Rumusan Masalah", "minor", "none")
def trc003(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    rqs = research_questions(makalah, ctx)
    tuj = tujuan_items(makalah, ctx)
    found = tujuan_subbab(makalah)
    if not rqs or not tuj or not found:
        return []
    loc = Location(bab=found[0], subbab=found[2].judul)
    if len(rqs) != len(tuj):
        return [make_finding("TRC-003", loc, f"Jumlah Tujuan ({len(tuj)}) tidak sama dengan jumlah RM ({len(rqs)}).")]
    out = []
    generic = _generic()
    for k, (q, t) in enumerate(zip(rqs, tuj), 1):
        a = {x for x in content_tokens(q) if x not in generic}
        b = {x for x in content_tokens(t) if x not in generic}
        ov = len(a & b) / max(1, min(len(a), len(b)))
        if ov < ctx.th("trc003_min_overlap"):
            out.append(make_finding("TRC-003", loc, f"Tujuan-{k} kurang sejalan dengan RM-{k} (tumpang-tindih "
                                    f"{ov:.2f}).", clip(t)))
    return out
