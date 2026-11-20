"""Perbaikan otomatis AMAN (tanpa LLM): hanya aturan `fix="auto"` yang tidak butuh memahami makna.

- LNG-001 (pola `fix=="auto"`: "di gamifikasi" -> "digamifikasi", kata fungsi ganda, "Bekalang", spasi ganda...) pada isi paragraf/butir.
  Judul sub-bab TIDAK pernah diubah (judul = kunci state; lihat docs/enhancing-engine.md RC-08).
- STR-002: butir pengantar ("...berikut:") dan paragraf penjelasan panjang dibuang dari daftar RM/Tujuan bila tersisa >=2 butir.

Mengembalikan salinan; objek asli tidak diubah.
"""
from malas.crews.models.TaskOutput import ContentList, ContentText, Makalah, SubBab
from malas.enhance.lint import LintContext, run_lints
from malas.enhance.lint.language import PATTERNS, _applies, replacement
from malas.enhance.models import Finding

_DAFTAR_JUDUL = ("rumusan masalah", "tujuan", "manfaat", "saran")
MAX_BUTIR_CHARS = 300


def _fix_text(text: str, makalah: Makalah, ctx: LintContext, bab_key: str) -> tuple[str, int]:
    n = 0
    for p in PATTERNS:
        if p.fix != "auto" or not _applies(p, makalah, ctx, bab_key):
            continue

        def sub(m, p=p):
            nonlocal n
            r = replacement(p, m)
            if r is None or r == m.group(0):
                return m.group(0)
            n += 1
            return r

        text = p.pattern.sub(sub, text)
    return text, n


def _is_daftar(sb: SubBab) -> bool:
    return sb.kind == "daftar" or any(k in sb.judul.lower() for k in _DAFTAR_JUDUL)


def _clean_butir(items: list[str]) -> list[str]:
    keep = [i for i in items if not i.rstrip().endswith(":") and len(i) <= MAX_BUTIR_CHARS]
    return keep if len(keep) >= 2 else items


def apply_auto_fixes(makalah: Makalah, ctx: LintContext | None = None) -> tuple[Makalah, list[Finding], int]:
    """-> (makalah baru, temuan tersisa dari `run_lints`, jumlah perubahan)."""
    ctx = ctx or LintContext()
    new = makalah.model_copy(deep=True)
    changes = 0
    for key, bab in new.bab.items():
        for sb in bab.subbab:
            for c in sb.content:
                if isinstance(c, ContentText):
                    c.isi, n = _fix_text(c.isi, new, ctx, key)
                    changes += n
                elif isinstance(c, ContentList):
                    fixed = [_fix_text(i, new, ctx, key) for i in c.items]
                    c.items = [t for t, _ in fixed]
                    changes += sum(n for _, n in fixed)
                    if _is_daftar(sb):
                        cleaned = _clean_butir(c.items)
                        changes += len(c.items) - len(cleaned)
                        c.items = cleaned
    return new, run_lints(new, ctx=ctx), changes
