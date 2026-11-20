"""CIT-001..003: integritas & atribusi sitasi (memakai `malas.citations`, perilakunya tidak diubah)."""
from __future__ import annotations

import re

from malas.citations import check_citations, citation_label, content_text, find_suspects
from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import RefIndex, card_for, item_texts, iter_subbab, sentences
from malas.enhance.lint.redundancy import fingerprints
from malas.enhance.models import Finding, Location

_SUSPECT_NAME = re.compile(r"^\(?\s*([A-ZÀ-Ý])\.?\s")


def _candidates(makalah: Makalah, raw: str) -> list[str]:
    """Referensi yang mungkin dimaksud sitasi ber-nama-1-huruf: tahun sama + penulis bertoken terakhir huruf itu.

    Hanya petunjuk untuk penambal (label benar dari `citation_label`), bukan perbaikan otomatis.
    """
    m = _SUSPECT_NAME.match(raw)
    y = re.search(r"(?:1[89]|20)\d{2}", raw)
    if not m or not y:
        return []
    letter, year = m.group(1), int(y.group(0))
    out = []
    for ref in makalah.daftar_pustaka:
        if ref.year != year:
            continue
        if any("," not in a and a.split() and a.split()[-1].rstrip(".") == letter for a in ref.authors):
            out.append(citation_label(ref))
    return out


@rule("CIT-001", "Sitasi-mirip yang tak terurai (suspect) atau tak ada di daftar pustaka", "blocker", "patch")
def cit001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out: list[Finding] = []
    report = check_citations(makalah)
    for key, _, sub in iter_subbab(makalah):
        counts: dict[str, int] = {}
        for s in find_suspects(content_text(sub.content)):
            counts[s] = counts.get(s, 0) + 1
        for raw, n in counts.items():
            cand = _candidates(makalah, raw)
            hint = (f"Ganti dengan label sah {cand[0]}." if len(cand) == 1 else
                    "Cocokkan ke entri daftar pustaka atau hapus klaimnya; jangan menebak penulis.")
            out.append(make_finding("CIT-001", Location(bab=key, subbab=sub.judul),
                                    f"Sitasi {raw} tidak dapat dicocokkan ke daftar pustaka ({n}x di sub-bab ini).",
                                    raw, hint=hint))
        inv: dict[str, int] = {}
        for raw in report.invalid.get(sub.judul, []):
            inv[raw] = inv.get(raw, 0) + 1
        for raw, n in inv.items():
            out.append(make_finding("CIT-001", Location(bab=key, subbab=sub.judul),
                                    f"Sitasi {raw} tidak ada di daftar pustaka ({n}x di sub-bab ini).", raw,
                                    hint="Gunakan hanya label sitasi dari daftar pustaka."))
    return out


@rule("CIT-002", "Referensi tak dikutip (akan/terancam dipangkas)", "info", "none")
def cit002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    report = check_citations(makalah)
    if not report.used_refs:  # tak satu pun sitasi cocok: prune juga tidak berjalan; jangan berisik
        return []
    note = " Pemangkasan ditahan karena ada sitasi tak terurai." if report.suspect else ""
    return [make_finding("CIT-002", Location(subbab="Daftar Pustaka", paragraph=i),
                         f"Referensi tidak dikutip di teks: \"{makalah.daftar_pustaka[i].title}\".{note}",
                         makalah.daftar_pustaka[i].title)
            for i in report.unused_refs]


@rule("CIT-003", "Atribusi: sitasi di luar referensi sub-bab atau angka milik kartu sumber lain", "major", "patch")
def cit003(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out: list[Finding] = []
    idx = RefIndex.of(makalah)
    refs = makalah.daftar_pustaka
    assigned = {t for r in refs for t in r.sections}
    for key, _, sub in iter_subbab(makalah):
        own = {i for i, r in enumerate(refs) if sub.judul in r.sections}
        for p, text in item_texts(sub):
            for sent in sentences(text):
                cited = idx.cited(sent)
                # (a) sub-bab punya alokasi referensi (refsearch) tetapi menyitir referensi alokasi sub-bab lain
                if sub.judul in assigned:
                    for raw, hits in cited:
                        if hits and not (set(hits) & own) and all(refs[h].sections for h in hits):
                            out.append(make_finding(
                                "CIT-003", Location(bab=key, subbab=sub.judul, paragraph=p),
                                f"{raw} bukan referensi yang dialokasikan untuk sub-bab ini; periksa atribusinya.",
                                sent, severity="minor",
                                hint="Pastikan klaim memang dari sumber itu (bukan sumber sub-bab ini)."))
                # (b) angka di kalimat persis milik key_result kartu sumber LAIN, bukan sumber yang disitir
                if not makalah.evidence:
                    continue
                fps = fingerprints(sent)
                cited_ids = {h for _, hits in cited for h in hits}
                if not fps or not cited_ids:
                    continue
                for fp, shown in fps.items():
                    mine = [card_for(makalah, i) for i in cited_ids]
                    if any(c and fp in fingerprints(c.key_result) for c in mine):
                        continue
                    other = [i for i in range(len(refs)) if i not in cited_ids and (c := card_for(makalah, i))
                             and fp in fingerprints(c.key_result)]
                    if other:
                        out.append(make_finding(
                            "CIT-003", Location(bab=key, subbab=sub.judul, paragraph=p),
                            f"Angka {shown} tercatat di kartu {citation_label(refs[other[0]])}, bukan sumber yang "
                            "disitir.", sent, hint=f"Atribusikan ke {citation_label(refs[other[0]])} atau hapus."))
    return out
