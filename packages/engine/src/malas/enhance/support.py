"""Cek dukungan-sumber (S20, tier deep): kalimat bersitasi berangka/kausal vs bukti sumbernya.

Tahap 1 (0 token): tumpang-tindih token antara kalimat dan teks bukti (judul + abstrak + kartu) -> kalimat berisiko.
Tahap 2 (1 panggilan, <=12 kalimat): LLM menilai didukung/sebagian/tidak. Hasil -> Finding CIT-003 (major) untuk "tidak".
"""
import json
import re
from collections.abc import Callable

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.budget import Budget, estimate_tokens
from malas.enhance.lint._util import RefIndex, content_tokens, item_texts, iter_subbab, sentences
from malas.enhance.models import Finding, Location
from malas.tolerant import extract_json

MAX_BATCH = 12
OUT_RESERVE = 900
MIN_OVERLAP = 0.25
_CITE_YEAR = re.compile(r"\([^()]*\b(?:1[89]|20)\d{2}[a-z]?[^()]*\)|\b(?:1[89]|20)\d{2}[a-z]?\b")
_RISK = re.compile(r"\d|%|membuktikan|terbukti|menyebabkan|signifikan|berhasil|meningkat|menurun", re.IGNORECASE)


def _evidence_text(state: Makalah, idx: int) -> str:
    from malas.enhance.evidence import ref_key_of
    ref = state.daftar_pustaka[idx]
    card = state.evidence.get(ref_key_of(ref))
    return " ".join(x for x in (ref.title, ref.excerpt or "", card.key_result if card else "", card.limitations if card else "") if x)


def candidates(state: Makalah) -> list[tuple[str, int, str, str]]:
    """(judul sub-bab, indeks konten, kalimat, teks bukti) untuk kalimat berisiko dengan tumpang-tindih rendah."""
    index = RefIndex.of(state)
    out = []
    for _, _, sb in iter_subbab(state):
        for i, text in item_texts(sb):
            for s in sentences(text):
                if not _RISK.search(_CITE_YEAR.sub("", s)):  # tahun dalam sitasi bukan "angka klaim"
                    continue
                refs = index.cited_refs(s)
                if not refs:
                    continue
                ev = _evidence_text(state, min(refs))
                q = set(content_tokens(s))
                if len(q & set(content_tokens(ev))) / max(1, len(q)) < MIN_OVERLAP:
                    out.append((sb.judul, i, s, ev[:500]))
    return out[:MAX_BATCH]


def run_support_check(state: Makalah, llm_call: Callable[[str], str], budget: Budget | None = None,
                      is_fatal: Callable[[Exception], bool] | None = None) -> list[Finding]:
    cands = candidates(state)
    if not cands:
        return []
    rows = "\n".join(f"{n}. KALIMAT: {s}\n   BUKTI: {ev}" for n, (_, _, s, ev) in enumerate(cands, 1))
    prompt = ("Nilai apakah tiap KALIMAT didukung oleh BUKTI sumbernya. Jawab HANYA JSON: "
              '{"hasil": [{"n": 1, "verdict": "didukung|sebagian|tidak"}]}\n' + rows)
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
    obj = extract_json(out)
    rows_out = obj.get("hasil") if isinstance(obj, dict) else None
    findings = []
    for r in rows_out if isinstance(rows_out, list) else []:
        if not isinstance(r, dict) or str(r.get("verdict")).lower() != "tidak":
            continue
        n = r.get("n")
        if isinstance(n, int) and 1 <= n <= len(cands):
            judul, par, sent, _ = cands[n - 1]
            findings.append(Finding(rule_id="CIT-003", severity="major", where=Location(subbab=judul, paragraph=par),
                                    message="Klaim bersitasi tampak tidak didukung teks sumbernya.", evidence=sent[:200],
                                    fix="patch", hint="Lunakkan klaim atau sesuaikan dengan isi sumber.", source="critic"))
    return findings


def mock_response(n: int = 0) -> str:
    return json.dumps({"hasil": []})
