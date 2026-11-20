"""Blueprint (kerangka argumen): 1 panggilan planner (docs/enhancing-engine.md §7 S11).

LLM hanya MENGUSULKAN kerangka; kode memvalidasi terhadap sub-bab nyata (kunci fiktif dibuang). Gagal = None dan
alur berjalan tanpa blueprint. Blueprint hanya memandu penulis; ia bukan sumber fakta.
"""
import re
from collections.abc import Callable

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.budget import Budget, estimate_tokens
from malas.enhance.models import Blueprint, Scope
from malas.refsearch.plan import strip_number
from malas.tolerant import extract_json

OUT_RESERVE = 900
MAX_RQ = 3


def build_prompt(state: Makalah) -> str:
    titles = "\n".join(f"- {sb.judul}" for b in state.bab.values() for sb in b.subbab)
    refs = "\n".join(f"- {r.title} ({r.year})" for r in state.daftar_pustaka[:15]) or "(belum ada)"
    rq = "\n".join(f"- {q}" for q in (state.blueprint.research_questions if state.blueprint else [])) or "(belum ada)"
    lingkup = "; ".join(x for x in (f"subjek: {state.subjek}" if state.subjek else "",
                                    f"jenjang: {state.jenjang}" if state.jenjang else "") if x) or "tidak ditentukan"
    return (
        "Anda perancang kerangka argumen makalah akademik. Susun kerangka SINGKAT (tanpa menulis isi makalah).\n"
        f'Judul: "{state.judul}"\nMata kuliah: "{state.mata_kuliah}"\nJenis: {state.jenis_makalah}\nLingkup dari pengguna: {lingkup}\n'
        f"Sub-bab (gunakan judul PERSIS ini):\n{titles}\n\nReferensi yang tersedia (judul, tahun):\n{refs}\n\n"
        f"Rumusan masalah usulan awal:\n{rq}\n\n"
        "Jawab HANYA JSON valid:\n"
        '{"research_questions": ["<=3 kalimat tanya"], '
        '"rq_map": {"<rumusan masalah persis>": ["<judul sub-bab Bab II yang menjawab>"]}, '
        '"subbab_tasks": {"<judul sub-bab persis>": "tugas argumen 1-2 kalimat, sertakan SATU sisi kritis/keterbatasan '
        'dan bedakan hasil belajar, persepsi, dan motivasi bila relevan"}, '
        '"domain_checklist": ["3-6 istilah/contoh WAJIB khas bidang topik ini"], '
        '"avoid_repeat": ["<=5 klaim/angka yang cukup dibahas di SATU sub-bab"]}'
    )


def _norm(t: str) -> str:
    return re.sub(r"\W+", " ", strip_number(t).lower()).strip()


def parse_blueprint(raw: str, state: Makalah) -> Blueprint | None:
    obj = extract_json(raw or "")
    if not isinstance(obj, dict):
        return None
    real = {_norm(sb.judul): sb.judul for b in state.bab.values() for sb in b.subbab}

    def real_title(t) -> str | None:
        return real.get(_norm(str(t)))

    rqs = [str(q).strip() for q in (obj.get("research_questions") or []) if isinstance(q, str) and q.strip()][:MAX_RQ]
    if not rqs and state.blueprint:
        rqs = list(state.blueprint.research_questions)[:MAX_RQ]
    rq_map: dict[str, list[str]] = {}
    for q, subs in (obj.get("rq_map") or {}).items() if isinstance(obj.get("rq_map"), dict) else []:
        match = next((r for r in rqs if _norm(r) == _norm(str(q))), None)
        valid = [t for t in (real_title(x) for x in (subs if isinstance(subs, list) else [subs])) if t]
        if match and valid:
            rq_map[match] = valid
    tasks = {}
    for t, task in (obj.get("subbab_tasks") or {}).items() if isinstance(obj.get("subbab_tasks"), dict) else []:
        rt = real_title(t)
        if rt and isinstance(task, str) and task.strip():
            tasks[rt] = " ".join(task.split())[:300]
    checklist = [" ".join(str(x).split())[:40] for x in (obj.get("domain_checklist") or []) if str(x).strip()][:6]
    avoid = [" ".join(str(x).split())[:120] for x in (obj.get("avoid_repeat") or []) if str(x).strip()][:5]
    if not (rqs or tasks or checklist):
        return None
    old = state.blueprint
    return Blueprint(scope=old.scope if old else Scope(jenis_makalah=state.jenis_makalah, subjek=state.subjek,
                                                       jenjang=state.jenjang),
                     research_questions=rqs, rq_map=rq_map, subbab_tasks=tasks, domain_checklist=checklist,
                     avoid_repeat=avoid)


def mock_response(state: Makalah) -> str:
    """Jawaban deterministik untuk mode uji (tanpa LLM)."""
    import json
    subs = [sb.judul for b in state.bab.values() for sb in b.subbab]
    return json.dumps({
        "research_questions": ["Bagaimana konsep dasar topik ini?", "Bagaimana dampaknya?"],
        "rq_map": {}, "subbab_tasks": {t: "Jelaskan dengan bukti dan sebut satu keterbatasan." for t in subs[:3]},
        "domain_checklist": ["istilah kunci", "contoh konkret", "keterbatasan"], "avoid_repeat": []})


def build_blueprint(state: Makalah, llm_call: Callable[[str], str], budget: Budget | None = None,
                    is_fatal: Callable[[Exception], bool] | None = None) -> Blueprint | None:
    """Blueprint baru, atau None (anggaran habis / gagal / tak terbaca). Galat fatal dilempar."""
    old = state.blueprint
    if old and (old.subbab_tasks or old.domain_checklist):
        return old  # resume: jangan ulangi
    prompt = build_prompt(state)
    est = estimate_tokens(prompt) + OUT_RESERVE
    if budget is not None and not budget.reserve(est):
        return None
    out = ""
    try:
        out = str(llm_call(prompt) or "")
    except Exception as e:
        if is_fatal and is_fatal(e):
            raise
        return None
    finally:
        if budget is not None:
            budget.settle(est, estimate_tokens(prompt) + estimate_tokens(out))
    return parse_blueprint(out, state)
