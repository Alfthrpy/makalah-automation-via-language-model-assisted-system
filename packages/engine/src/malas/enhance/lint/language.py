"""LNG-001: daftar kecil regex terkurasi untuk salah ketik/kalimat janggal (bertes satu per satu).

Setiap pola punya `fix`: "auto" hanya bila penggantiannya aman tanpa memahami makna (dipakai `autofix`);
selebihnya "human". Judul sub-bab tidak pernah diubah otomatis (judul = kunci state, RC-08).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import bab_order, has_citation, item_texts, iter_subbab, sentences
from malas.enhance.models import Finding, Location

Repl = str | Callable[[re.Match], str]

_FUNC_WORDS = ["yang", "dan", "di", "ke", "dari", "untuk", "pada", "dalam", "ini", "itu", "dengan", "atau", "adalah", "juga", "tidak", "akan", "sebagai", "oleh", "bahwa", "secara", "serta"]


@dataclass(frozen=True)
class LangPattern:
    id: str
    pattern: re.Pattern
    message: str
    repl: Repl | None = None  # None = tanpa saran otomatis
    fix: str = "human"
    severity: str = "minor"
    scope: str = "all"  # all | bab_i_iii (hanya Bab I & III: rujukan "penelitian ini" = makalah sendiri)
    profile: str | None = None  # hanya untuk profil ini (mis. kajian_pustaka)


def _join_di(m: re.Match) -> str:
    return "di" + m.group(1)


# "di" + kata kerja pasif ber-akhiran -kan / -isasi / -ikasi ditulis terpisah ("di gamifikasi" -> "digamifikasi").
# Daftar pengecualian: kata benda tempat ber-akhiran sama (jarang, tetapi jangan diubah).
_DI_EXCEPT = r"(?!ikan\b|pangkalan\b|pelabuhan\b|perusahaan\b|lapangan\b|perkebunan\b|kawasan\b|kalangan\b)"
PATTERNS: list[LangPattern] = [
    LangPattern("di-pasif", re.compile(rf"\bdi\s+{_DI_EXCEPT}([a-z]+(?:kan|isasi|ifikasi|ikasi))\b"),
                "Awalan pasif \"di-\" ditulis serangkai", _join_di, fix="auto"),
    LangPattern("kata-ulang", re.compile(rf"\b({'|'.join(_FUNC_WORDS)})\s+\1\b", re.IGNORECASE),
                "Kata fungsi terulang", lambda m: m.group(1), fix="auto"),
    LangPattern("kata-ulang-lain", re.compile(rf"\b(?!(?:{'|'.join(_FUNC_WORDS)})\b)([a-z]{{3,}})\s+\1\b"),
                "Kata terulang (periksa apakah salah ketik)", None),
    LangPattern("spasi-ganda", re.compile(r"(?<=\S)[ \t]{2,}(?=\S)"), "Spasi ganda", " ", fix="auto",
                severity="info"),
    LangPattern("spasi-tanda-baca", re.compile(r"(?<=\w)\s+([,.;:])(?=\s|$)"), "Spasi sebelum tanda baca",
                lambda m: m.group(1), fix="auto", severity="info"),
    LangPattern("latar-bekalang", re.compile(r"\b[Bb]ekalang\b"), "Salah ketik \"bekalang\" (belakang)",
                lambda m: "Belakang" if m.group(0)[0] == "B" else "belakang", fix="auto"),
    LangPattern("dilatarbelakangi", re.compile(r"\bdilatar\s+belakangi\b"), "Tulis serangkai \"dilatarbelakangi\"",
                "dilatarbelakangi", fix="auto"),
    LangPattern("tidak-baku", re.compile(r"\b(praktek|resiko|analisa|merubah|dirubah|sekedar|mempengaruhi|"
                                         r"dipengaruhinya|nafas|kwalitas|obyek|subyek|tehnik|jaman)\b", re.IGNORECASE),
                "Bentuk tidak baku (KBBI)", None, severity="info"),
    LangPattern("penelitian-ini", re.compile(r"\b(?:penelitian\s+ini|tujuan\s+penelitian)\b", re.IGNORECASE),
                "Makalah kajian pustaka menyebut dirinya \"penelitian\"", None, scope="bab_i_iii",
                profile="kajian_pustaka"),
]
_BAKU = {"praktek": "praktik", "resiko": "risiko", "analisa": "analisis", "merubah": "mengubah", "dirubah": "diubah",
         "sekedar": "sekadar", "mempengaruhi": "memengaruhi", "nafas": "napas", "kwalitas": "kualitas",
         "obyek": "objek", "subyek": "subjek", "tehnik": "teknik", "jaman": "zaman"}

BY_ID = {p.id: p for p in PATTERNS}


def replacement(p: LangPattern, m: re.Match) -> str | None:
    if p.repl is None:
        return None
    return p.repl(m) if callable(p.repl) else p.repl


def _suggest(p: LangPattern, m: re.Match) -> str:
    r = replacement(p, m)
    if r is not None:
        return r
    if p.id == "tidak-baku":
        return _BAKU.get(m.group(1).lower(), "")
    if p.id == "penelitian-ini":
        return "makalah ini" if "ini" in m.group(0).lower() else "tujuan penulisan"
    return ""


def _applies(p: LangPattern, makalah: Makalah, ctx: LintContext, bab_key: str) -> bool:
    if p.profile and (ctx.profile or makalah.jenis_makalah or "").strip().lower() != p.profile:
        return False
    return not (p.scope == "bab_i_iii" and bab_order(bab_key) not in (1, 3))


@rule("LNG-001", "Salah ketik/kalimat janggal dari daftar regex terkurasi", "minor", "auto")
def lng001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out: list[Finding] = []
    for key, _, sub in iter_subbab(makalah):
        for p in PATTERNS:
            if not _applies(p, makalah, ctx, key):
                continue
            # judul: hanya dilaporkan, tidak diubah otomatis (kunci state)
            m = p.pattern.search(sub.judul)
            if m and p.id not in ("spasi-ganda", "spasi-tanda-baca"):
                out.append(make_finding("LNG-001", Location(bab=key, subbab=sub.judul),
                                        f"Judul: {p.message} (\"{m.group(0)}\" -> \"{_suggest(p, m)}\").",
                                        m.group(0), severity=p.severity, fix="human"))
            for i, text in item_texts(sub):
                for m in p.pattern.finditer(text):
                    if p.id == "penelitian-ini" and any(m.group(0) in s and has_citation(s) for s in sentences(text)):
                        continue  # "penelitian ini" merujuk studi yang disitir, bukan makalah
                    sug = _suggest(p, m)
                    arrow = f" -> \"{sug}\"" if sug else ""
                    out.append(make_finding(
                        "LNG-001", Location(bab=key, subbab=sub.judul, paragraph=i),
                        f"{p.message}: \"{m.group(0)}\"{arrow}.", m.group(0), severity=p.severity, fix=p.fix,
                        hint=f"{('Ganti menjadi ' + repr(sug) + ' ') if sug else ''}[lng:{p.id}]"))
    return out
