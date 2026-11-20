"""Gerbang mutu penulis (S16/S17): guardrail crewAI berbasis lint, dengan soft-fail.

crewAI 1.x menjalankan `Task.guardrails=[fn]`; bila `(False, umpan_balik)` agen yang sama mengulang dengan umpan balik
itu, dan saat percobaan ulang HABIS crewAI melempar Exception (task.py `_invoke_guardrail_function`) sehingga job mati.
Karena itu fungsi di sini selalu `(True, hasil)` pada pemanggilan terakhir (soft-fail): temuan yang tersisa dicatat
dan ditangkap lagi oleh tahap "Cek mutu".
"""
from collections.abc import Callable
from typing import Any

from malas.crews.models.TaskOutput import Makalah, SubBab
from malas.enhance.lint import run_lints
from malas.enhance.models import Finding
from malas.tolerant import ParseError, parse_subbab

GATE_RULES = ("CIT-001", "CLM-001", "CLM-004", "RED-001", "STR-002")
BAD = ("blocker", "major")


def check_candidate(state: Makalah, judul: str, content: list) -> list[Finding]:
    """Temuan lint (aturan gerbang) hanya untuk sub-bab `judul` bila isinya diganti `content`."""
    probe = state.model_copy(deep=True)
    for bab in probe.bab.values():
        for sb in bab.subbab:
            if sb.judul == judul:
                sb.content = content
    return [f for f in run_lints(probe, only=GATE_RULES, ctx={"source": "state"})
            if f.where.subbab == judul and f.severity in BAD]


def feedback_text(findings: list[Finding]) -> str:
    lines = [f"- {f.message}" + (f" Saran: {f.hint}" if f.hint else "") for f in findings[:6]]
    return ("Perbaiki masalah berikut pada sub-bab ini lalu kembalikan SELURUH konten dalam format yang sama "
            "(JSON sesuai skema SubBab). Jangan menambah fakta/sumber baru, gunakan HANYA sitasi dari daftar referensi:\n"
            + "\n".join(lines))


def make_guardrail(get_ctx: Callable[[], dict | None], max_retries: int = 1) -> Callable[[Any], tuple[bool, Any]]:
    """`get_ctx()` -> {"state": Makalah, "judul": str, "report": list|None} untuk sub-bab yang sedang ditulis.

    Pemanggilan ke-(max_retries+1) selalu lolos (soft-fail) dan menyimpan temuan sisa ke `ctx["report"]`.
    """
    calls = {"n": 0, "judul": None}

    def guardrail(output: Any) -> tuple[bool, Any]:
        ctx = get_ctx()
        if not ctx:
            return True, output
        if calls["judul"] != ctx["judul"]:
            calls["n"], calls["judul"] = 0, ctx["judul"]
        calls["n"] += 1
        last = calls["n"] > max_retries
        sub: SubBab | None = getattr(output, "pydantic", None)
        if sub is None:  # crewAI 1.15: pada pemanggilan PERTAMA `pydantic` belum terisi (konversi menyusul); baca dari raw
            try:
                sub = parse_subbab(getattr(output, "raw", "") or "")
            except (ParseError, ValueError):
                sub = None
        if sub is None or not sub.content:
            return (True, output) if last else (False, "Keluaran harus JSON sesuai skema SubBab (field content tidak kosong).")
        findings = check_candidate(ctx["state"], ctx["judul"], sub.content)
        if not findings:
            return True, output
        if last:
            if ctx.get("report") is not None:
                ctx["report"].extend(findings)
            return True, output
        return False, feedback_text(findings)

    return guardrail
