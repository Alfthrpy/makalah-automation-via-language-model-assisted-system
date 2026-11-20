"""STR-001..004: penomoran judul, butir RM/Tujuan, bagian wajib per profil, tembok paragraf."""
from __future__ import annotations

import re

from malas.crews.models.TaskOutput import ContentList, ContentTable, Makalah, SubBab
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import (
    bab_order,
    find_subbabs,
    fold,
    is_question,
    iter_subbab,
    kesimpulan_subbab,
    list_items,
    paragraphs,
    sub_text,
    title_core,
)
from malas.enhance.models import Finding, Location

_DUP_NUM = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s+\1\b\.?\s*")
_NUM = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s+")
_INTRO = re.compile(r"(?::\s*$)|\bsebagai\s+berikut\b|\bantara\s+lain\s*:?\s*$", re.IGNORECASE)

RM_KEYS = ("rumusan masalah", "rumusan", "pertanyaan penelitian")
TUJUAN_KEYS = ("tujuan",)

# Bagian wajib per profil (S12): (bab, kata kunci judul alternatif, label). "keterbatasan" juga diterima sebagai
# kalimat di Bab III karena profil menaruhnya di Kesimpulan.
REQUIRED = {
    "kajian_pustaka": [
        ("I", ("manfaat",), "Manfaat"),
        ("I", ("metode", "metodologi"), "Metode Penulisan"),
        ("III", ("saran", "rekomendasi"), "Saran"),
        ("III", ("keterbatasan",), "Keterbatasan"),
    ],
}


def rm_subbab(makalah: Makalah) -> tuple[str, int, SubBab] | None:
    hit = find_subbabs(makalah, *RM_KEYS)
    return hit[0] if hit else None


def tujuan_subbab(makalah: Makalah) -> tuple[str, int, SubBab] | None:
    hit = [h for h in find_subbabs(makalah, *TUJUAN_KEYS) if bab_order(h[0]) == 1]
    return hit[0] if hit else None


def classify_items(sub: SubBab, question: bool, max_chars: int) -> list[tuple[int, str, str]]:
    """Butir daftar -> (indeks konten, teks, peran) dengan peran: intro | item | outro | bad.

    - intro: butir PERTAMA bergaya pengantar (berakhiran ":" / "sebagai berikut").
    - outro: butir di EKOR yang panjang (>max_chars) atau (RM) bukan kalimat tanya, setelah butir sah terakhir.
    - bad  : butir di tengah yang panjang atau (RM) bukan kalimat tanya.
    """
    items = list_items(sub)
    roles = []
    for k, (i, t) in enumerate(items):
        if _INTRO.search(t.strip()) and not is_question(t):
            roles.append("intro" if all(r == "intro" for r in roles) else "bad")
        elif len(t) > max_chars or (question and not is_question(t)):
            roles.append("bad")
        else:
            roles.append("item")
    if "item" in roles:
        last = max(k for k, r in enumerate(roles) if r == "item")
        roles = [("outro" if (k > last and r == "bad") else r) for k, r in enumerate(roles)]
    return [(i, t, r) for (i, t), r in zip(items, roles)]


@rule("STR-001", "Penomoran judul sub-bab ganda (\"2.1 2.1\") atau tidak urut", "minor", "auto")
def str001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out = []
    for key, i, sub in iter_subbab(makalah):
        loc = Location(bab=key, subbab=sub.judul)
        if _DUP_NUM.match(sub.judul):
            out.append(make_finding("STR-001", loc, f"Nomor judul tercetak ganda: \"{sub.judul}\".", sub.judul,
                                    hint="Hapus nomor yang berulang."))
            continue
        m = _NUM.match(sub.judul)
        expected = f"{bab_order(key)}.{i + 1}"
        if m and bab_order(key) < 99 and m.group(1) != expected:
            out.append(make_finding("STR-001", loc, f"Nomor judul {m.group(1)} tidak sesuai urutan (harusnya "
                                    f"{expected}).", sub.judul, fix="human"))
    return out


@rule("STR-002", "Butir RM/Tujuan: pengantar/penjelasan ikut jadi butir, atau RM bukan kalimat tanya", "major", "auto")
def str002(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    out: list[Finding] = []
    max_chars = int(ctx.th("str002_max_item_chars"))
    for found, question, label in ((rm_subbab(makalah), True, "Rumusan masalah"),
                                   (tujuan_subbab(makalah), False, "Tujuan")):
        if not found:
            continue
        key, _, sub = found
        cls = classify_items(sub, question, max_chars)
        has_item = any(r == "item" for _, _, r in cls)
        for i, t, r in cls:
            loc = Location(bab=key, subbab=sub.judul, paragraph=i)
            if r == "intro":
                out.append(make_finding("STR-002", loc, f"{label}: kalimat pengantar ikut menjadi butir daftar.", t,
                                        fix="auto" if has_item else "patch",
                                        hint="Jadikan paragraf pengantar, bukan butir."))
            elif r == "outro":
                out.append(make_finding("STR-002", loc, f"{label}: paragraf penjelasan ({len(t)} karakter) ikut "
                                        "menjadi butir daftar.", t, fix="auto" if has_item else "patch",
                                        hint="Pindahkan penjelasan ke paragraf setelah daftar."))
            elif r == "bad":
                why = "bukan kalimat tanya" if question and not is_question(t) else f"terlalu panjang ({len(t)})"
                out.append(make_finding("STR-002", loc, f"{label}: butir {why}.", t, fix="patch",
                                        hint="Rumuskan sebagai satu kalimat tanya ringkas." if question else
                                        "Ringkas menjadi satu kalimat tujuan."))
    return out


def _profile(makalah: Makalah, ctx: LintContext) -> str:
    return (ctx.profile or makalah.jenis_makalah or "kajian_pustaka").strip().lower()


@rule("STR-003", "Bagian wajib menurut profil dokumen tidak ada (Metode, Manfaat, Saran, Keterbatasan)", "major",
      "none")
def str003(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    req = REQUIRED.get(_profile(makalah, ctx))
    if not req or not makalah.bab:
        return []
    out = []
    concl = kesimpulan_subbab(makalah)
    for bab, keys, label in req:
        if find_subbabs(makalah, *keys, bab=bab):
            continue
        if label == "Keterbatasan" and concl and "keterbatasan" in fold(sub_text(concl[2])):
            continue
        out.append(make_finding("STR-003", Location(bab=bab), f"Bagian \"{label}\" belum ada di Bab {bab}.",
                                hint=f"Tambahkan sub-bab {label} (outline profil {_profile(makalah, ctx)})."))
    return out


@rule("STR-004", "Sub-bab Bab II terlalu banyak paragraf tanpa daftar/tabel/sub-judul", "minor", "none")
def str004(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    n_max = int(ctx.th("str004_max_paragraphs"))
    out = []
    for key, _, sub in iter_subbab(makalah):
        if bab_order(key) != 2:
            continue
        if any(isinstance(c, (ContentList, ContentTable)) for c in sub.content):
            continue
        n = len(paragraphs(sub))
        if n > n_max:
            out.append(make_finding("STR-004", Location(bab=key, subbab=sub.judul),
                                    f"{n} paragraf berturut-turut tanpa daftar/tabel/sub-judul ({title_core(sub.judul)}).",
                                    hint="Pecah dengan sub-judul atau sajikan sintesis studi sebagai tabel."))
    return out
