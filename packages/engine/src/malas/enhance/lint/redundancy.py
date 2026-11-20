"""RED-001 (fakta numerik/daftar nama berulang antar sub-bab) dan RED-002 (paragraf nyaris sama)."""
from __future__ import annotations

import re

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import fold, item_texts, iter_subbab, paragraphs, title_core, words
from malas.enhance.models import Finding, Location

_NUM = r"\d+(?:[.,]\d+)?"
_FP_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("F", re.compile(rf"\bF\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*{_NUM}")),
    ("t", re.compile(rf"\bt\s*\(\s*\d+\s*\)\s*=\s*-?{_NUM}")),
    ("p", re.compile(r"\bp\s*[=<]\s*0?[,.]\d+")),
    ("eta", re.compile(rf"(?:η²|η2|eta\s*squared|\beta²)\s*\)?\s*(?:=|sebesar)\s*{_NUM}", re.IGNORECASE)),
    ("r", re.compile(r"\br\s*=\s*-?0?[,.]\d+")),
    ("n", re.compile(r"\b[nN]\s*=\s*\d+")),
    ("n", re.compile(r"\b\d{2,5}\s+(?:siswa|mahasiswa|responden|peserta(?:\s+didik)?|guru|partisipan|santri|"
                     r"subjek|sampel)\b", re.IGNORECASE)),
    ("pct", re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d+)?\s?%")),
    ("ci", re.compile(rf"(?:CI|IK)\s*\d*\s*%?\s*:?\s*\[?{_NUM}\s*[–\-]\s*{_NUM}\]?")),
    ("mean", re.compile(rf"\b(?:M|rata-rata)\s*=\s*{_NUM}")),
]
# daftar nama diri (>=3 butir berkapital dipisah koma), mis. daftar platform "Quizizz, Quizlet, Kahoot"
_NAME = r"[A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?"
_NAME_LIST = re.compile(rf"{_NAME}(?:\s*,\s*{_NAME}){{2,}}(?:\s*,?\s*(?:dan|serta|&)\s+{_NAME})?")
_MIN_SHARED_NAMES = 3


def _norm_fp(kind: str, s: str) -> str:
    s = s.replace("η2", "η²").replace(",", ".")
    s = re.sub(r"\s+", "", s.casefold())
    if kind == "n":
        num = re.search(r"\d+", s)
        return f"n={num.group(0)}" if num else s
    if kind == "eta":
        num = re.search(r"\d*\.?\d+$", s)
        return f"eta={num.group(0)}" if num else s
    if kind == "pct":
        return s.replace("%", "") + "%"
    return s


def fingerprints(text: str) -> dict[str, str]:
    """Sidik jari fakta numerik -> teks aslinya. "F(1,67) = 8.52" dan "F(1, 67)=8,52" sama."""
    out: dict[str, str] = {}
    for kind, pat in _FP_PATTERNS:
        for m in pat.finditer(text or ""):
            fp = _norm_fp(kind, m.group(0))
            if kind == "pct" and fp in {"100%", "0%", "50%"}:  # persen generik, terlalu umum
                continue
            out.setdefault(fp, " ".join(m.group(0).split()))
    return out


def name_lists(text: str) -> list[set[str]]:
    """Himpunan nama per daftar nama diri (>=3 nama) di teks."""
    out = []
    for m in _NAME_LIST.finditer(text or ""):
        names = {fold(n.strip()) for n in re.split(r"\s*,\s*|\s+(?:dan|serta|&)\s+", m.group(0)) if n.strip()}
        if len(names) >= _MIN_SHARED_NAMES:
            out.append(names)
    return out


@rule("RED-001", "Fakta numerik / daftar nama yang sama muncul di >=2 sub-bab", "major", "patch")
def red001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    seen: dict[str, dict[tuple[str, str], tuple[int, str]]] = {}  # fp -> {(bab, judul): (paragraf, teks)}
    shown: dict[str, str] = {}
    lists: list[tuple[tuple[str, str], int, set[str]]] = []
    for key, _, sub in iter_subbab(makalah):
        for p, text in item_texts(sub):
            for fp, s in fingerprints(text).items():
                seen.setdefault(fp, {}).setdefault((key, sub.judul), (p, s))
                shown.setdefault(fp, s)
            lists.extend(((key, sub.judul), p, names) for names in name_lists(text))
    # kelompokkan sidik jari menurut himpunan sub-bab tempat muncul -> satu temuan per kelompok fakta
    groups: dict[tuple[tuple[str, str], ...], list[str]] = {}
    for fp, locs in seen.items():
        if len(locs) >= 2:
            groups.setdefault(tuple(locs), []).append(fp)
    out: list[Finding] = []
    for locs, fps in groups.items():
        out.append(_finding(makalah, locs, [shown[f] for f in sorted(fps)], seen[min(fps)]))
    # daftar nama: gabungkan daftar yang berbagi >=3 nama
    used = [False] * len(lists)
    for i, (loc_i, p_i, names_i) in enumerate(lists):
        if used[i]:
            continue
        cluster = {loc_i: p_i}
        common = set(names_i)
        for j in range(i + 1, len(lists)):
            loc_j, p_j, names_j = lists[j]
            if not used[j] and len(names_i & names_j) >= _MIN_SHARED_NAMES:
                used[j] = True
                cluster.setdefault(loc_j, p_j)
                common &= names_j
        if len(cluster) >= 2:
            locs = tuple(cluster)
            first = locs[0]
            label = ", ".join(sorted(common))[:80] if len(common) >= _MIN_SHARED_NAMES else "daftar nama"
            out.append(_finding(makalah, locs, [f"daftar [{label}]"], {first: (cluster[first], "")}))
    return out


def _finding(makalah: Makalah, locs, facts: list[str], where_map) -> Finding:
    first = locs[0]
    titles = [title_core(j) or j for _, j in locs]
    only_concl = all("simpulan" in fold(t) for t in titles[1:])
    para = where_map.get(first, (None, ""))[0] if isinstance(where_map, dict) else None
    return make_finding(
        "RED-001", Location(bab=first[0], subbab=first[1], paragraph=para),
        f"Fakta {'; '.join(facts)} diulang di {len(locs)} sub-bab: {', '.join(titles)}.",
        "; ".join(facts), severity="minor" if only_concl else None,
        hint="Sajikan fakta sekali di sub-bab paling relevan; di tempat lain rujuk saja (mis. 'lihat 2.4').")


def _shingles(text: str, k: int = 5) -> set[tuple[str, ...]]:
    w = words(text)
    return {tuple(w[i:i + k]) for i in range(len(w) - k + 1)}


@rule("RED-002", "Paragraf nyaris sama antar sub-bab (Jaccard shingling 5-kata)", "major", "patch")
def red002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    th = ctx.th("red002_jaccard")
    paras = []
    for key, _, sub in iter_subbab(makalah):
        for p, text in paragraphs(sub):
            sh = _shingles(text)
            if len(sh) >= 10:  # paragraf sangat pendek tidak dibandingkan
                paras.append((key, sub.judul, p, sh, text))
    out: list[Finding] = []
    for i in range(len(paras)):
        for j in range(i + 1, len(paras)):
            a, b = paras[i], paras[j]
            if (a[0], a[1]) == (b[0], b[1]):
                continue
            jac = len(a[3] & b[3]) / len(a[3] | b[3])
            if jac > th:
                out.append(make_finding(
                    "RED-002", Location(bab=b[0], subbab=b[1], paragraph=b[2]),
                    f"Paragraf ini nyaris sama (Jaccard {jac:.2f}) dengan {title_core(a[1])} ¶{a[2]}.", b[4],
                    hint="Hapus pengulangan atau tulis ulang dengan sudut pandang/temuan baru."))
    return out
