"""REF-001..003: kelengkapan APA, urutan/kapitalisasi, dan keragaman daftar pustaka."""
from __future__ import annotations

from malas.apa import apa_sort_key, to_sentence_case
from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import words
from malas.enhance.models import Finding, Location

_DP = "Daftar Pustaka"
# penanda judul berbahasa Indonesia (kata fungsi khas; "di"/"dan" juga ada di Melayu, cukup untuk rasio kasar)
_ID_WORDS = {"dan", "yang", "dalam", "untuk", "pada", "terhadap", "dengan", "di", "melalui", "pembelajaran",
             "pendidikan", "siswa", "bahasa", "penerapan", "pengaruh", "pengembangan", "berbasis", "sebagai"}
_EN_WORDS = {"the", "of", "and", "in", "for", "on", "with", "a", "an", "to", "learning", "students", "education"}


@rule("REF-001", "Entri APA tak lengkap (tanpa nama jurnal/volume/halaman/tautan)", "minor", "auto")
def ref001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    """Satu temuan ringkas per daftar (bukan per entri) agar tidak berisik."""
    refs = makalah.daftar_pustaka
    if not refs:
        return []
    no_venue = [i for i, r in enumerate(refs) if not (r.venue or "").strip()]
    no_vol = [i for i, r in enumerate(refs) if (r.venue or "").strip() and r.source != "arxiv"
              and not ((r.volume or "").strip() and (r.pages or "").strip())]
    no_link = [i for i, r in enumerate(refs) if not (r.doi or r.link)]
    out = []
    if no_venue:
        out.append(make_finding(
            "REF-001", Location(subbab=_DP, paragraph=no_venue[0]),
            f"{len(no_venue)} dari {len(refs)} entri tanpa nama jurnal/penerbit; format APA tidak lengkap.",
            refs[no_venue[0]].title, hint="Lengkapi venue/volume/halaman dari metadata DOI (OpenAlex/Crossref)."))
    if no_vol:
        out.append(make_finding(
            "REF-001", Location(subbab=_DP, paragraph=no_vol[0]),
            f"{len(no_vol)} entri berjurnal tanpa volume/halaman.", refs[no_vol[0]].title, severity="info"))
    if no_link:
        out.append(make_finding("REF-001", Location(subbab=_DP, paragraph=no_link[0]),
                                f"{len(no_link)} entri tanpa DOI/tautan.", refs[no_link[0]].title, severity="info",
                                fix="human"))
    return out


@rule("REF-002", "Daftar pustaka tak berurut alfabet / judul huruf KAPITAL atau Title Case", "minor", "auto")
def ref002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    """Pada `source="state"` konverter (S03) sudah mengurutkan & sentence-case saat render -> keparahan info."""
    refs = makalah.daftar_pustaka
    sev = "info" if ctx.source == "state" else None
    note = " (dirapikan otomatis saat render)" if ctx.source == "state" else ""
    out = []
    keys = [apa_sort_key(r.model_dump()) for r in refs]
    bad = [i for i in range(1, len(keys)) if keys[i] < keys[i - 1]]
    if bad:
        out.append(make_finding("REF-002", Location(subbab=_DP, paragraph=bad[0]),
                                f"Daftar pustaka tidak berurut alfabet nama penulis pertama{note}.",
                                refs[bad[0]].title, severity=sev))
    caps = [i for i, r in enumerate(refs) if to_sentence_case(r.title) != r.title]
    if caps:
        upper = sum(1 for i in caps if sum(c.isupper() for c in refs[i].title) >
                    0.6 * max(1, sum(c.isalpha() for c in refs[i].title)))
        out.append(make_finding(
            "REF-002", Location(subbab=_DP, paragraph=caps[0]),
            f"{len(caps)} judul tidak sentence case APA ({upper} di antaranya huruf KAPITAL){note}.",
            refs[caps[0]].title, severity=sev))
    return out


def _is_indonesian(title: str) -> bool:
    w = words(title)
    ide = sum(1 for x in w if x in _ID_WORDS)
    en = sum(1 for x in w if x in _EN_WORDS)
    return ide > en


@rule("REF-003", "Rasio referensi berbahasa Indonesia tinggi pada topik non-lokal / tanpa karya landmark", "major",
      "none")
def ref003(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    """`indo` dari rencana refsearch: False -> major; None (tak diketahui) -> info. Landmark butuh `cited_by`."""
    refs = makalah.daftar_pustaka
    if len(refs) < 4 or ctx.indo is True:
        return []
    out = []
    ratio = sum(_is_indonesian(r.title) for r in refs) / len(refs)
    if ratio > ctx.th("ref003_indo_ratio"):
        out.append(make_finding(
            "REF-003", Location(subbab=_DP),
            f"{ratio:.0%} referensi berjudul Indonesia; sumber internasional/karya dasar kurang beragam.",
            severity=None if ctx.indo is False else "info",
            hint="Tambahkan sumber internasional dan karya teori dasar (landmark) yang relevan."))
    cited = [getattr(r, "cited_by", None) for r in refs]
    if any(c is not None for c in cited):
        thr = ctx.th("ref003_landmark_cited_by")
        if not any((c or 0) >= thr for c in cited):
            out.append(make_finding("REF-003", Location(subbab=_DP),
                                    f"Tidak ada karya landmark (dikutip >= {int(thr)}x) di daftar pustaka.",
                                    severity="minor"))
    return out
