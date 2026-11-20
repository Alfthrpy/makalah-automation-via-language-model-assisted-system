"""CLM-001..004: klaim melebihi bukti, tanpa sisi kritis, klaim tanpa sitasi, motivasi vs hasil belajar."""
from __future__ import annotations

import re

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import (
    RefIndex,
    bab_order,
    card_for,
    has_citation,
    item_texts,
    iter_subbab,
    paragraphs,
    sentences,
    title_core,
)
from malas.enhance.models import EvidenceCard, Finding, Location

# Leksikon kausal/penguat (CLM-001). Bentuk berimbuhan ditulis eksplisit agar mudah diuji.
CAUSAL = re.compile(
    r"\b(?:membuktikan|dibuktikan|terbukti|menyebabkan|disebabkan\s+oleh|berhasil\s+mengatasi|"
    r"jelas\s+menunjukkan|secara\s+signifikan\s+meningkatkan|signifikan\s+meningkatkan|tidak\s+diragukan|"
    r"dipastikan|pasti\s+meningkatkan|selalu\s+meningkatkan|efektif\s+meningkatkan|ampuh|menjamin|"
    r"berdampak\s+langsung)\b", re.IGNORECASE)

# Sisi kritis/keterbatasan (CLM-002). Kuat = cukup sendiri; konsesif hanya dihitung bila kalimatnya juga memuat
# kata keterbatasan bukti (kalibrasi: "Namun, di sisi lain, tantangan muncul ..." BUKAN kritik atas bukti).
CRIT_STRONG = re.compile(
    r"\b(?:keterbatasan|kelemahan|terbatas(?:nya)?|tidak\s+semua|perlu\s+kehati-hatian|hati-hati|kritik|"
    r"kontradiktif|bertentangan|masih\s+beragam|belum\s+konsisten|tidak\s+konsisten|bias|efek\s+kebaruan|"
    r"novelty|overjustification|risiko|dampak\s+negatif|tidak\s+signifikan|belum\s+tentu|perlu\s+diuji|"
    r"tanpa\s+kelompok\s+kontrol|sampel\s+kecil|generalisasi)\b", re.IGNORECASE)
CONCESSIVE = re.compile(r"\b(?:namun|akan\s+tetapi|meskipun|walaupun|sebaliknya|di\s+sisi\s+lain)\b", re.IGNORECASE)
_LIMIT_WORDS = re.compile(r"\b(?:tidak|belum|kurang|tantangan|kendala|masalah|sulit|terbatas)\b", re.IGNORECASE)

# Kalimat bergaya klaim faktual (CLM-003): generalisasi/kuantitatif/evaluatif
CLAIMY = re.compile(
    r"\b(?:banyak|sebagian\s+besar|mayoritas|umumnya|pada\s+umumnya|sering(?:\s+kali)?|seringkali|rendah(?:nya)?|"
    r"tinggi(?:nya)?|meningkat|menurun|terbukti|menunjukkan|berdampak|efektif|signifikan|cenderung|"
    r"telah\s+(?:banyak|diterapkan|terbukti)|diidentifikasi|gagal|berkembang\s+pesat|krusial)\b|\d", re.IGNORECASE)
_META = re.compile(r"\b(?:makalah\s+ini|sub-?bab|bab\s+ini|pembahasan\s+ini|kajian\s+ini|uraian\s+(?:di\s+)?atas|"
                   r"oleh\s+karena\s+itu|dengan\s+demikian|berdasarkan\s+(?:uraian|pembahasan))\b", re.IGNORECASE)
_ANAPHORA = re.compile(r"\b(?:penelitian|studi|kajian|temuan|tinjauan|analisis|hasil)\s+(?:ini|tersebut)\b|"
                       r"\bmereka\b", re.IGNORECASE)

MOTIVASI = re.compile(r"\b(?:motivasi|termotivasi|memotivasi)\b", re.IGNORECASE)


def _cards(makalah: Makalah, ids: set[int]) -> list[EvidenceCard]:
    return [c for i in sorted(ids) if (c := card_for(makalah, i))]


def _sentence_refs(idx: RefIndex, sent: str, para_refs: set[int]) -> set[int]:
    own = idx.cited_refs(sent)
    if own:
        return own
    return set(para_refs) if len(para_refs) == 1 else set()  # kalimat lanjutan dalam paragraf bersumber tunggal


@rule("CLM-001", "Kata kausal/penguat pada kalimat yang menyitir sumber berdesain non-kausal (kartu)", "major", "patch",
      needs="evidence")
def clm001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    if not makalah.evidence:
        return []
    idx = RefIndex.of(makalah)
    out = []
    for key, _, sub in iter_subbab(makalah):
        for p, text in paragraphs(sub):
            para_refs = idx.cited_refs(text)
            for sent in sentences(text):
                m = CAUSAL.search(sent)
                if not m:
                    continue
                cards = _cards(makalah, _sentence_refs(idx, sent, para_refs))
                weak = [c for c in cards if not c.causal_ok]
                if not weak or any(c.causal_ok for c in cards):
                    continue
                strong = any(c.confidence in ("sedang", "tinggi") for c in weak)
                c = weak[0]
                out.append(make_finding(
                    "CLM-001", Location(bab=key, subbab=sub.judul, paragraph=p),
                    f"\"{m.group(0)}\" untuk sumber berdesain {c.design.replace('_', '-')}"
                    f"{' tanpa kontrol' if c.has_control is False else ''}: klaim melebihi bukti.", sent,
                    severity=None if strong else "info",
                    hint="Gunakan bahasa terkalibrasi (mis. 'menunjukkan peningkatan pada sampel ...') dan sebut "
                         "keterbatasan desain."))
    return out


def _is_critical(sent: str) -> bool:
    if CRIT_STRONG.search(sent):
        return True
    return bool(CONCESSIVE.search(sent) and _LIMIT_WORDS.search(sent) and re.search(
        r"\b(?:bukti|temuan|penelitian|studi|data|hasil|gamifikasi|penerapan|efektivitas|dampak)\b", sent, re.IGNORECASE))


@rule("CLM-002", "Sub-bab Bab II tanpa kalimat keterbatasan/kontra", "minor", "patch")
def clm002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out = []
    for key, _, sub in iter_subbab(makalah):
        if bab_order(key) != 2 or not sub.content:
            continue
        sents = [s for _, t in item_texts(sub) for s in sentences(t)]
        if sents and not any(_is_critical(s) for s in sents):
            out.append(make_finding("CLM-002", Location(bab=key, subbab=sub.judul),
                                    f"Tidak ada kalimat keterbatasan/pandangan kontra di {title_core(sub.judul)}.",
                                    hint="Tambahkan satu sisi kritis yang bersumber (keterbatasan desain, hasil "
                                         "berbeda, risiko)."))
    return out


def _is_claim(sent: str) -> bool:
    return (len(sent.split()) >= 8 and not sent.rstrip().endswith("?") and not _META.search(sent)
            and bool(CLAIMY.search(sent)))


def _claim_scope(makalah: Makalah):
    for key, i, sub in iter_subbab(makalah):
        if (bab_order(key) == 1 and i == 0) or bab_order(key) == 2:
            yield key, sub


@rule("CLM-003", "Rasio kalimat bergaya klaim tanpa sitasi di 1.1 & Bab II melebihi ambang", "minor", "patch")
def clm003(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    ratio_th, min_claims = ctx.th("clm003_ratio"), int(ctx.th("clm003_min_claims"))
    out = []
    for key, sub in _claim_scope(makalah):
        claims, uncited, first = 0, 0, None
        for p, text in paragraphs(sub):
            prev_cited = False
            for sent in sentences(text):
                cited = has_citation(sent)
                if _is_claim(sent):
                    claims += 1
                    attributed = cited or (prev_cited and _ANAPHORA.search(sent))
                    if not attributed:
                        uncited += 1
                        if first is None:
                            first = (p, sent)
                prev_cited = cited or (prev_cited and bool(_ANAPHORA.search(sent)))
        if claims >= min_claims and uncited / claims > ratio_th and first:
            out.append(make_finding(
                "CLM-003", Location(bab=key, subbab=sub.judul, paragraph=first[0]),
                f"{uncited} dari {claims} kalimat bergaya klaim tanpa sitasi di {title_core(sub.judul)}.", first[1],
                hint="Beri sitasi pada klaim faktual/generalisasi atau lunakkan menjadi pendapat penulis."))
    return out


@rule("CLM-004", "Klaim motivasi disitir ke sumber yang mengukur hasil belajar (kartu)", "major", "patch",
      needs="evidence")
def clm004(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    if not makalah.evidence:
        return []
    idx = RefIndex.of(makalah)
    out = []
    for key, _, sub in iter_subbab(makalah):
        for p, text in paragraphs(sub):
            for sent in sentences(text):
                if not MOTIVASI.search(sent):
                    continue
                cards = _cards(makalah, idx.cited_refs(sent))
                if cards and all(c.outcome == "hasil_belajar" for c in cards):
                    out.append(make_finding(
                        "CLM-004", Location(bab=key, subbab=sub.judul, paragraph=p),
                        "Klaim tentang motivasi disitir ke sumber yang mengukur hasil belajar.", sent,
                        hint="Bedakan hasil belajar dari motivasi; jangan menyimpulkan motivasi dari skor tes."))
    return out
