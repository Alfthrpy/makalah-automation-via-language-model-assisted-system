"""Kritik terarah (S18): SATU panggilan LLM atas seluruh makalah -> temuan berlokasi (source="critic").

LLM hanya menunjuk masalah; setiap temuan divalidasi kode (sub-bab/paragraf harus ada, maks 12, bukan duplikat lint).
Tidak ada teks yang diubah di sini: perbaikan lewat `patch.py` dengan penerimaan monoton.
"""
import json
import re
from collections.abc import Callable

from malas.citations import citation_label
from malas.crews.models.TaskOutput import ContentTable, Makalah
from malas.enhance.budget import Budget, estimate_tokens
from malas.enhance.evidence import card_brief, ref_key_of
from malas.enhance.lint._util import item_texts, iter_subbab
from malas.enhance.models import Finding, Location
from malas.tolerant import extract_json

MAX_FINDINGS = 12
OUT_RESERVE = 1500
PARA_CHARS = 900
RUBRIC = (
    "Periksa: (1) setiap rumusan masalah terjawab di Kesimpulan dan sub-bab hasil; (2) kekuatan klaim sepadan desain studi "
    "(tanpa kontrol/kualitatif tidak boleh 'membuktikan'); (3) ada sisi kritis/keterbatasan; (4) istilah/contoh khas bidang "
    "muncul; (5) pengulangan angka/paragraf antar sub-bab; (6) bagian yang melebar dari judul/rumusan masalah; "
    "(7) populasi/subjek konsisten dengan bukti.")


def render_paper(state: Makalah) -> str:
    out = []
    for key, _, sb in iter_subbab(state):
        out.append(f"## [{key}] {sb.judul}")
        for i, t in item_texts(sb):
            out.append(f"[¶{i}] " + (t if len(t) <= PARA_CHARS else t[:PARA_CHARS] + "…"))
        out.extend(f"[tabel] {c.caption}" for c in sb.content if isinstance(c, ContentTable))
    return "\n".join(out)


def build_prompt(state: Makalah, lint_findings: list[Finding]) -> str:
    rq = "\n".join(f"- {q}" for q in (state.blueprint.research_questions if state.blueprint else [])) or "(lihat Bab I)"
    cards = "\n".join(
        f"- {citation_label(r)}: {card_brief(c)['desain']}, kausal={card_brief(c)['boleh_kausal']}, outcome={card_brief(c)['outcome']}"
        for r in state.daftar_pustaka if (c := state.evidence.get(ref_key_of(r)))) or "(tidak ada)"
    known = "\n".join(f"- {f.rule_id} @ {f.where.subbab or '-'}: {f.message[:80]}" for f in lint_findings[:25]) or "(tidak ada)"
    return (
        "Anda reviewer akademik. Tinjau makalah di bawah dan laporkan masalah KONKRET yang belum tercantum pada daftar "
        f"temuan otomatis.\n{RUBRIC}\n\nRumusan masalah:\n{rq}\n\nKartu bukti:\n{cards}\n\n"
        f"Temuan otomatis (jangan diulang):\n{known}\n\nMAKALAH:\n{render_paper(state)}\n\n"
        f'Jawab HANYA JSON: {{"findings": [{{"subbab": "<judul persis>", "paragraph": <nomor ¶ atau null>, '
        f'"severity": "major|minor", "message": "<=160 karakter", "hint": "instruksi perbaikan 1 kalimat"}}]}} '
        f"(maksimal {MAX_FINDINGS}, urut paling penting; kosongkan bila tidak ada).")


def parse_findings(raw: str, state: Makalah, known: list[Finding]) -> list[Finding]:
    obj = extract_json(raw or "")
    rows = obj.get("findings") if isinstance(obj, dict) else obj if isinstance(obj, list) else None
    if not isinstance(rows, list):
        return []
    sub_bab = {sb.judul: (key, len(sb.content)) for key, _, sb in iter_subbab(state)}
    seen = {(f.where.subbab, re.sub(r"\W+", " ", f.message.lower())[:40]) for f in known}
    out: list[Finding] = []
    for r in rows:
        if not isinstance(r, dict) or r.get("subbab") not in sub_bab:
            continue
        key, n = sub_bab[r["subbab"]]
        msg = " ".join(str(r.get("message") or "").split())[:200]
        if not msg:
            continue
        par = r.get("paragraph")
        par = par if isinstance(par, int) and 0 <= par < n else None
        sig = (r["subbab"], re.sub(r"\W+", " ", msg.lower())[:40])
        if sig in seen:
            continue
        seen.add(sig)
        sev = "major" if str(r.get("severity")).lower() == "major" else "minor"
        out.append(Finding(rule_id="CRT-001", severity=sev, where=Location(bab=key, subbab=r["subbab"], paragraph=par),
                           message=msg, fix="patch", hint=" ".join(str(r.get("hint") or "").split())[:300],
                           source="critic"))
        if len(out) >= MAX_FINDINGS:
            break
    return out


def mock_response(state: Makalah) -> str:
    return json.dumps({"findings": []})


def run_critic(state: Makalah, lint_findings: list[Finding], llm_call: Callable[[str], str], budget: Budget | None = None,
               is_fatal: Callable[[Exception], bool] | None = None) -> list[Finding]:
    prompt = build_prompt(state, lint_findings)
    est = estimate_tokens(prompt) + OUT_RESERVE
    if budget is not None and not budget.reserve(est):
        return []
    out = ""
    try:
        out = str(llm_call(prompt) or "")
    except Exception as e:
        if is_fatal and is_fatal(e):
            raise
        return []
    finally:
        if budget is not None:
            budget.settle(est, estimate_tokens(prompt) + estimate_tokens(out))
    return parse_findings(out, state, lint_findings)
