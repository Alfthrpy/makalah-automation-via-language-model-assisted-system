"""Penambal terarah (S19): tulis ulang HANYA sub-bab bermasalah, terima bila lebih baik (monoton).

Penerimaan: skor temuan lint berbobot untuk sub-bab itu turun, tak ada blocker baru, panjang teks wajar (60-140%).
Selain itu teks asli dipertahankan dan penolakan dicatat. Satu putaran, maks `max_patches` sub-bab, berbatas anggaran.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from malas.citations import citation_label, content_text
from malas.crews.models.TaskOutput import ContentTable, Makalah, SubBab
from malas.enhance.budget import Budget, estimate_tokens
from malas.enhance.lint import run_lints
from malas.enhance.lint._util import iter_subbab
from malas.enhance.models import SEVERITY_WEIGHT, Finding
from malas.tolerant import ParseError, parse_subbab

OUT_RESERVE = 1800
MIN_RATIO, MAX_RATIO = 0.6, 1.4


@dataclass
class PatchReport:
    accepted: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    skipped_budget: int = 0


def _local(state: Makalah, judul: str) -> list[Finding]:
    return [f for f in run_lints(state, ctx={"source": "state"}) if f.where.subbab == judul]


def _score(fs: list[Finding]) -> int:
    return sum(SEVERITY_WEIGHT[f.severity] for f in fs)


def build_prompt(state: Makalah, sub: SubBab, findings: list[Finding]) -> str:
    refs = "\n".join(f"- {citation_label(r)} {r.title} ({r.year})" for r in state.daftar_pustaka)
    todo = "\n".join(f"- {f.message}" + (f" -> {f.hint}" if f.hint else "") for f in findings[:6])
    return (
        f'Perbaiki sub-bab "{sub.judul}" dari makalah "{state.judul}". Terapkan HANYA perbaikan berikut, pertahankan isi, '
        f"urutan, dan struktur lainnya:\n{todo}\n\nAturan: jangan menambah fakta/sumber baru; sitasi hanya dari daftar "
        f"referensi (salin bentuk persis); jangan mengulang angka yang sudah ada di sub-bab lain; bahasa Indonesia formal.\n"
        f"Daftar referensi:\n{refs}\n\nTEKS SAAT INI:\n{content_text(sub.content)}\n\n"
        'Kembalikan SELURUH sub-bab sebagai JSON: {"content": [{"type": "text", "isi": "..."}, '
        '{"type": "list", "title_items": null, "items": ["..."]}]}')


def _tables(sub: SubBab) -> list:
    return [c for c in sub.content if isinstance(c, ContentTable)]


def patch_subbab(state: Makalah, sub: SubBab, findings: list[Finding], llm_call: Callable[[str], str],
                 budget: Budget | None, is_fatal: Callable[[Exception], bool] | None = None) -> str:
    """-> "accepted" | "rejected" | "budget". Mengubah `sub.content` hanya bila diterima."""
    prompt = build_prompt(state, sub, findings)
    est = estimate_tokens(prompt) + OUT_RESERVE
    if budget is not None and not budget.reserve(est):
        return "budget"
    out = ""
    try:
        out = str(llm_call(prompt) or "")
    except Exception as e:
        if is_fatal and is_fatal(e):
            raise
        return "rejected"
    finally:
        if budget is not None:
            budget.settle(est, estimate_tokens(prompt) + estimate_tokens(out))
    try:
        cand = parse_subbab(out).content
    except (ParseError, ValueError):
        return "rejected"
    old_len, new_len = len(content_text(sub.content)), len(content_text(cand))
    if not old_len or not (MIN_RATIO <= new_len / old_len <= MAX_RATIO):
        return "rejected"
    before = _local(state, sub.judul)
    original = sub.content
    sub.content = cand + _tables(sub)  # tabel rakitan kode dipertahankan
    after = _local(state, sub.judul)
    new_blocker = sum(f.severity == "blocker" for f in after) > sum(f.severity == "blocker" for f in before)
    if _score(after) < _score(before) and not new_blocker:
        return "accepted"
    sub.content = original
    return "rejected"


def run_patches(state: Makalah, findings: list[Finding], llm_call: Callable[[str], str], budget: Budget | None,
                max_patches: int = 3, is_fatal: Callable[[Exception], bool] | None = None) -> PatchReport:
    """Tambal sub-bab dengan temuan `fix=="patch"` (major+ dulu), maks `max_patches`; satu putaran."""
    by_sub: dict[str, list[Finding]] = {}
    for f in findings:
        if f.fix == "patch" and f.severity in ("blocker", "major") and f.where.subbab:
            by_sub.setdefault(f.where.subbab, []).append(f)
    order = sorted(by_sub, key=lambda j: -_score(by_sub[j]))[:max_patches]
    titles = {sb.judul: sb for _, _, sb in iter_subbab(state)}
    rep = PatchReport()
    for judul in order:
        res = patch_subbab(state, titles[judul], by_sub[judul], llm_call, budget, is_fatal)
        if res == "accepted":
            rep.accepted.append(judul)
        elif res == "budget":
            rep.skipped_budget += 1
        else:
            rep.rejected.append(judul)
    return rep
