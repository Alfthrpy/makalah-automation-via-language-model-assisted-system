"""ContextPack: konteks penulis per sub-bab, dibangun KODE (tanpa LLM). Rancangan: docs/enhancing-engine.md §7 S08.

Masalah yang diperbaiki (RC-03): dulu penulis hanya melihat isi PENUH sub-bab sebelumnya (±1.000 token) dan hanya bila
`i>0` di bab yang sama, sehingga 2.1 tak melihat Bab I (RM) dan 3.1 Kesimpulan tak melihat apa pun. Sekarang tiap sub-bab
menerima ringkasan ekstraktif yang lebih pendek (±300-700 token) tetapi mencakup SELURUH makalah yang sudah ditulis:
struktur, rumusan masalah, "ledger" (kalimat pertama + angka yang sudah dipakai) dan, untuk Kesimpulan, ringkasan Bab II.
"""
import re

from malas.citations import content_text
from malas.crews.models.TaskOutput import ContentList, ContentText, Makalah, SubBab
from malas.enhance.models import ContextPack

LEDGER_CHARS = 1200  # ±300 token
DIGEST_CHARS = 1600  # ±400 token
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý\"“(])")
_FACT = re.compile(
    r"F\(\d+,\s*\d+\)\s*=\s*[\d,.]+|\bp\s*[=<]\s*0[,.]\d+|η²?\s*=\s*[\d,.]+|\bn\s*=\s*\d+|"
    r"\b\d+(?:[,.]\d+)?\s*%|\b\d+\s+(?:siswa|mahasiswa|responden|peserta|guru)\b", re.IGNORECASE)
_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-zA-Z][.)])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(" ".join(text.split())) if s.strip()]


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def facts_of(text: str) -> list[str]:
    seen: list[str] = []
    for m in _FACT.finditer(text):
        f = " ".join(m.group(0).split())
        if f.lower() not in (x.lower() for x in seen):
            seen.append(f)
    return seen


def rq_items(sub: SubBab) -> list[str]:
    """Butir rumusan masalah dari sub-bab 'Rumusan Masalah' (list, atau teks bermarker)."""
    items: list[str] = []
    for c in sub.content:
        if isinstance(c, ContentList):
            items += [i.strip() for i in c.items if i.strip()]
        elif isinstance(c, ContentText):
            lines = [ln for ln in c.isi.splitlines() if ln.strip()]
            marked = [_MARKER.sub("", ln, count=1).strip() for ln in lines if _MARKER.match(ln)]
            items += marked if len(marked) >= 2 else [ln.strip() for ln in lines]
    return [i for i in items if i.strip() and not i.rstrip().endswith(":")]


def _is_rm(judul: str) -> bool:
    return "rumusan masalah" in judul.lower()


def research_questions(state: Makalah) -> list[str]:
    """RM final: dari sub-bab yang sudah ditulis; bila belum, dari blueprint (kerangka)."""
    for bab in state.bab.values():
        for sb in bab.subbab:
            if _is_rm(sb.judul) and sb.content:
                items = rq_items(sb)
                if items:
                    return items[:5]
    return list(state.blueprint.research_questions[:5]) if state.blueprint else []


def _ledger(done: list[SubBab]) -> list[str]:
    if not done:
        return []
    per = max(90, LEDGER_CHARS // len(done))
    lines = []
    for sb in done:
        text = content_text(sb.content)
        sents = sentences(text)
        first = sents[0] if sents else ""
        facts = facts_of(text)
        extra = f" (angka: {'; '.join(facts[:6])})" if facts else ""
        lines.append(f"[{sb.judul}] {_clip(first, max(40, per - len(extra)))}{extra}")
    return lines


def _digest(bab2: list[SubBab]) -> list[str]:
    if not bab2:
        return []
    per = max(160, DIGEST_CHARS // len(bab2))
    out = []
    for sb in bab2:
        sents = sentences(content_text(sb.content))
        out.append(f"[{sb.judul}] {_clip(' '.join(sents[:2]), per)}")
    return out


def build_context(state: Makalah, current: SubBab, bab_key: str) -> ContextPack:
    """Konteks untuk menulis `current` (sub-bab pada bab `bab_key`)."""
    all_sub = [(k, sb) for k, b in state.bab.items() for sb in b.subbab]
    done = [sb for _, sb in all_sub if sb is not current and sb.content]
    pack = ContextPack(
        outline_titles=[sb.judul for _, sb in all_sub],
        rq=research_questions(state),
        ledger=_ledger(done),
    )
    if bab_key not in ("I", "II") and "II" in state.bab:  # Bab III (Kesimpulan/Saran): ringkasan hasil Bab II
        pack.digest_bab2 = _digest([sb for sb in state.bab["II"].subbab if sb.content])
    return pack


def render_context(pack: ContextPack) -> str:
    """Teks untuk placeholder `{previous_subab_contents}` di prompt penulis."""
    parts = ["Struktur makalah: " + " | ".join(pack.outline_titles)] if pack.outline_titles else []
    if pack.rq:
        parts.append("Rumusan masalah makalah ini:\n" + "\n".join(f"{i}) {q}" for i, q in enumerate(pack.rq, 1)))
    if pack.ledger:
        parts.append("Sudah dibahas di sub-bab lain (RINGKASAN; jangan diulang, cukup rujuk dengan 'lihat <sub-bab>'):\n"
                     + "\n".join(f"- {ln}" for ln in pack.ledger))
    if pack.digest_bab2:
        parts.append("Ringkasan hasil Bab II (dasar untuk menjawab TIAP rumusan masalah):\n"
                     + "\n".join(f"- {ln}" for ln in pack.digest_bab2))
    return "\n".join(parts)


def scope_text(state: Makalah) -> str:
    """Lingkup makalah untuk prompt; kosong bila tak ditentukan."""
    bits = []
    jenis = {"kajian_pustaka": "kajian pustaka (bukan penelitian lapangan)", "penelitian": "laporan penelitian"}.get(
        state.jenis_makalah, state.jenis_makalah)
    if jenis:
        bits.append(f"jenis: {jenis}")
    if state.subjek:
        bits.append(f"subjek/populasi: {state.subjek}")
    if state.jenjang:
        bits.append(f"jenjang: {state.jenjang}")
    return "; ".join(bits) if (state.subjek or state.jenjang) else (
        "tidak ditentukan; ikuti populasi pada bukti referensi dan JANGAN menyebut populasi/subjek yang tidak ada di bukti")


def one_line_refs(refs: list[dict]) -> list[dict]:
    """Referensi cadangan (sub-bab tanpa referensi sendiri): 1 baris per sumber, tanpa kutipan full-text."""
    out = []
    for r in refs:
        ex = sentences(r.get("excerpt") or "")
        out.append({"sitasi": r.get("sitasi"), "title": r.get("title"), "year": r.get("year"),
                    "excerpt": _clip(ex[0], 200) if ex else None})
    return out
