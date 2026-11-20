"""S15 Kartu Bukti (L2): ringkasan terstruktur per referensi (docs/enhancing-engine.md §7 S15).

Alur per referensi:
  1. Praproses TANPA LLM (regex): ukuran sampel, statistik, kata kunci desain/outcome/populasi.
  2. Satu panggilan LLM murah (peran `planner`) dengan judul + abstrak + <=1.500 karakter potongan full-text.
  3. Validasi oleh KODE (LLM tidak dipercaya untuk fakta):
     - `key_result` harus substring teks masukan (spasi diabaikan, tak peka huruf); bagian yang tidak -> dibuang;
     - `n` harus muncul di teks masukan;
     - `causal_ok` = desain rct/kuasi_eksperimen DAN `has_control` True (dipaksa kode, bukan LLM);
     - `basis` = "fulltext" bila potongan isi dipakai; `confidence` "rendah" bila hanya abstrak.
  Fallback (anggaran habis, mock tanpa LLM, galat, parse gagal): kartu heuristik dari regex, `confidence` "rendah".

Cache lintas pengguna kunci `ref_key` (DOI atau hash judul+tahun): isi kartu turunan sumber publik, BUKAN teks pengguna.
"""
import hashlib
import json
import re
import unicodedata
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from malas.enhance.budget import Budget, estimate_tokens
from malas.enhance.cache import KVCache
from malas.enhance.models import EvidenceCard
from malas.tolerant import extract_json

CACHE_NS = "evidence_card_v1"
PASSAGE_CHARS = 1500  # potongan full-text maksimum per kartu (masukan LLM)
ABSTRACT_CHARS = 2500
OUT_RESERVE = 250  # taksiran token keluaran yang dipesan dari anggaran sebelum memanggil LLM
# BM25 memakai token kata; full-text kebanyakan berbahasa Inggris, jadi padanan Inggris ikut dalam kueri
PASSAGE_QUERY = "metode sampel hasil keterbatasan method sample participants results limitation"
SOURCE_MARK = "=== SUMBER ==="

DESIGNS = ("rct", "kuasi_eksperimen", "pre_post", "survei", "kualitatif", "slr", "konseptual",
           "pengembangan_rnd", "lainnya", "tak_diketahui")
OUTCOMES = ("motivasi", "hasil_belajar", "persepsi", "lainnya", "tak_diketahui")
DESIGN_LABEL = {
    "rct": "RCT (uji acak terkontrol)", "kuasi_eksperimen": "kuasi-eksperimen", "pre_post": "pra-pascates tanpa kontrol",
    "survei": "survei", "kualitatif": "kualitatif", "slr": "tinjauan sistematis", "konseptual": "konseptual",
    "pengembangan_rnd": "pengembangan (R&D)", "lainnya": "lainnya", "tak_diketahui": "-",
}
OUTCOME_LABEL = {"motivasi": "motivasi", "hasil_belajar": "hasil belajar", "persepsi": "persepsi", "lainnya": "lainnya",
                 "tak_diketahui": "-"}

# --------------------------------------------------------------------------- praproses (regex, 0 token)
_N_EQ = re.compile(r"\b[nN]\s*=\s*(\d{1,6})\b")
_N_WORD = re.compile(
    r"\b(\d{1,6})\s+(siswa|peserta didik|mahasiswa|responden|peserta|guru|santri|students?|participants?|"
    r"respondents?|pupils?|teachers?|learners?|undergraduates?)\b", re.IGNORECASE)
_STAT = re.compile(
    r"F\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*\d+(?:[.,]\d+)?"
    r"|\bt\s*\(\s*\d+\s*\)\s*=\s*-?\d+(?:[.,]\d+)?"
    r"|\bp\s*[=<>≤]\s*0?[.,]\d+"
    r"|η²?\s*p?\s*=\s*0?[.,]\d+"
    r"|(?:95\s*%\s*)?\bCI\b\s*[=:]?\s*\[[^\]]{1,40}\]"
    r"|\b(?:Cohen'?s\s+)?d\s*=\s*-?\d+(?:[.,]\d+)?")
_POP = re.compile(
    r"\b(siswa|peserta didik|mahasiswa|guru|santri|students|pupils|teachers|learners|undergraduates)"
    r"(\s+(?:kelas\s+[\wIVX]+|SD|SMP|SMA|SMK|MI|MTs|MA|madrasah\s+\w+|sekolah\s+\w+|university|universitas\s+\w+|"
    r"of\s+(?:primary|secondary|high|junior|senior)\s+school))?", re.IGNORECASE)

_KW = {
    "slr": r"systematic (?:literature )?review|tinjauan (?:literatur|pustaka) sistematis|kajian literatur sistematis|"
           r"meta-?anal|\bprisma\b|scoping review",
    "rct": r"randomi[sz]ed (?:controlled )?trial|\brct\b|uji acak terkontrol|random assignment",
    "kuasi_eksperimen": r"quasi[- ]?experiment|kuasi[- ]?eksperimen|eksperimen semu",
    "pengembangan_rnd": r"research and development|\br\s?&\s?d\b|\baddie\b|\b4-?d model|model 4-?d|"
                        r"penelitian pengembangan|design[- ]based research|development research|"
                        r"pengembangan (?:media|produk|modul|bahan ajar)",
    "pre_post": r"pre-?test|post-?test|pra-?pasca|pra-?tes|pasca-?tes|one[- ]group",
    "survei": r"\bsurvei\b|\bsurvey|kuesioner|questionnaire|angket",
    "kualitatif": r"wawancara|observasi|kualitatif|qualitative|interview|studi kasus|case study|fenomenolog|"
                  r"phenomenolog|observation",
    "konseptual": r"konseptual|conceptual|framework|kerangka (?:teori|konsep)|theoretical|teoretis",
}
_KW_RE = {k: re.compile(v, re.IGNORECASE) for k, v in _KW.items()}
_EXPERIMENT = re.compile(r"eksperimen|experiment", re.IGNORECASE)
_CONTROL = re.compile(r"kelompok kontrol|kelas kontrol|control group|control class|comparison group|"
                      r"kelompok pembanding|kelas pembanding", re.IGNORECASE)
_OUTCOME_KW = {
    "hasil_belajar": re.compile(r"hasil belajar|prestasi|achievement|learning outcome|pemahaman|kemampuan|"
                                r"academic performance|test scores?|nilai", re.IGNORECASE),
    "motivasi": re.compile(r"motivasi|motivation|engagement|keterlibatan|minat", re.IGNORECASE),
    "persepsi": re.compile(r"persepsi|perception|attitude|sikap|tanggapan|kepuasan|satisfaction", re.IGNORECASE),
}


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def find_n(text: str) -> int | None:
    m = _N_EQ.search(text or "") or _N_WORD.search(text or "")
    return int(m.group(1)) if m else None


def find_stats(text: str) -> list[str]:
    out: list[str] = []
    for m in _STAT.finditer(text or ""):
        s = " ".join(m.group(0).split())
        if s not in out:
            out.append(s)
    return out


def guess_design(text: str) -> str:
    t = text or ""
    for key in ("slr", "rct", "kuasi_eksperimen"):
        if _KW_RE[key].search(t):
            return key
    if _EXPERIMENT.search(t) and _CONTROL.search(t):
        return "kuasi_eksperimen"  # konservatif: tanpa kata "acak" tidak dianggap RCT
    for key in ("pengembangan_rnd", "pre_post", "survei", "kualitatif", "konseptual"):
        if _KW_RE[key].search(t):
            return key
    return "tak_diketahui"


def guess_outcome(text: str) -> str:
    counts = {k: len(rx.findall(text or "")) for k, rx in _OUTCOME_KW.items()}
    best = max(counts.values()) if counts else 0
    if not best:
        return "tak_diketahui"
    return next(k for k in ("hasil_belajar", "motivasi", "persepsi") if counts[k] == best)


def guess_population(text: str) -> str:
    m = _POP.search(text or "")
    return " ".join(m.group(0).split())[:80] if m else ""


def preprocess(text: str) -> dict:
    """Petunjuk regex (tanpa LLM) dari teks sumber."""
    return {
        "design": guess_design(text),
        "has_control": True if _CONTROL.search(text or "") else None,
        "n": find_n(text),
        "stats": find_stats(text),
        "population": guess_population(text),
        "outcome": guess_outcome(text),
    }


# --------------------------------------------------------------------------- kunci & kartu
def ref_key_of(ref) -> str:
    """Kunci stabil sebuah referensi: 'doi:<doi kecil>' atau 't:<hash judul+tahun>'. Tidak memuat data pengguna."""
    doi = (getattr(ref, "doi", None) or "").strip().lower()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    if doi:
        return f"doi:{doi}"
    title = unicodedata.normalize("NFKD", getattr(ref, "title", "") or "")
    title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return "t:" + hashlib.sha1(f"{title}|{getattr(ref, 'year', '')}".encode()).hexdigest()[:16]


def _enforce(card: EvidenceCard) -> EvidenceCard:
    """Aturan yang dipaksa kode apa pun kata LLM."""
    card.causal_ok = card.design in ("rct", "kuasi_eksperimen") and card.has_control is True
    if card.basis == "abstrak":
        card.confidence = "rendah"
    return card


def heuristic_card(ref_key: str, text: str, basis: str = "abstrak") -> EvidenceCard:
    """Kartu tanpa LLM: semua isian dari regex (angka verbatim dari teks), confidence rendah."""
    h = preprocess(text)
    card = EvidenceCard(ref_key=ref_key, design=h["design"], has_control=h["has_control"], n=h["n"],
                        population=h["population"], outcome=h["outcome"], key_result="; ".join(h["stats"][:3]),
                        confidence="rendah", basis=basis)
    return _enforce(card)


def informative(card: EvidenceCard | None) -> bool:
    """Kartu punya isi yang berguna (bukan sekadar 'tak diketahui')."""
    return bool(card) and (card.design != "tak_diketahui" or card.n is not None or bool(card.key_result))


def _verify_result(key_result: str, source: str) -> str:
    """Pertahankan hanya bagian `key_result` (dipisah ';') yang benar-benar ada di teks sumber."""
    src = _norm_ws(source)
    keep = [p.strip() for p in re.split(r";", key_result or "") if p.strip() and _norm_ws(p) in src]
    return "; ".join(keep)[:200]


def _as_bool(v) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        low = v.strip().lower()
        if low in {"true", "ya", "yes", "ada"}:
            return True
        if low in {"false", "tidak", "no", "tidak ada"}:
            return False
    return None


def _as_int(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"\s*\d{1,6}\s*", v):
        return int(v)
    return None


def _pick(v, allowed, aliases: dict[str, str]) -> str:
    s = re.sub(r"[\s-]+", "_", str(v or "").strip().lower())
    s = aliases.get(s, s)
    return s if s in allowed else "tak_diketahui"


_DESIGN_ALIAS = {"kuasi": "kuasi_eksperimen", "quasi_experiment": "kuasi_eksperimen", "quasi_experimental":
                 "kuasi_eksperimen", "randomized": "rct", "pre_post_test": "pre_post", "pretest_posttest": "pre_post",
                 "survey": "survei", "qualitative": "kualitatif", "systematic_review": "slr", "r&d": "pengembangan_rnd",
                 "rnd": "pengembangan_rnd", "conceptual": "konseptual"}
_OUTCOME_ALIAS = {"hasil": "hasil_belajar", "learning_outcome": "hasil_belajar", "achievement": "hasil_belajar",
                  "motivation": "motivasi", "perception": "persepsi"}


def card_from_llm(raw: str, ref_key: str, source: str, basis: str) -> EvidenceCard | None:
    """Parse + validasi keluaran LLM. None bila bukan JSON objek."""
    data = extract_json(raw or "")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        return None
    hints = preprocess(source)
    n = _as_int(data.get("n"))
    if n is not None and not re.search(rf"(?<!\d){n}(?!\d)", source):
        n = None  # angka tak ada di teks -> halusinasi
    if n is None:
        n = hints["n"]
    conf = str(data.get("confidence") or "sedang").strip().lower()
    card = EvidenceCard(
        ref_key=ref_key,
        design=_pick(data.get("design"), DESIGNS, _DESIGN_ALIAS),
        has_control=_as_bool(data.get("has_control")),
        n=n,
        population=" ".join(str(data.get("population") or "").split())[:80],
        outcome=_pick(data.get("outcome"), OUTCOMES, _OUTCOME_ALIAS),
        key_result=_verify_result(str(data.get("key_result") or ""), source),
        limitations=" ".join(str(data.get("limitations") or "").split())[:200],
        confidence=conf if conf in ("rendah", "sedang", "tinggi") else "sedang",
        basis=basis,
    )
    if card.design == "tak_diketahui":
        card.design = hints["design"]
    return _enforce(card)


def build_prompt(ref, abstract: str, passage: str) -> str:
    hints = preprocess(f"{ref.title}\n{abstract}\n{passage}")
    hint_txt = (f"desain≈{hints['design']}, kontrol≈{hints['has_control']}, n≈{hints['n']}, "
                f"statistik: {'; '.join(hints['stats'][:4]) or '-'}")
    return (
        "Ekstrak KARTU BUKTI dari SATU sumber ilmiah. Gunakan HANYA teks sumber di bawah; jangan menebak.\n"
        "Keluarkan HANYA satu objek JSON dengan kunci:\n"
        '{"design": "rct|kuasi_eksperimen|pre_post|survei|kualitatif|slr|konseptual|pengembangan_rnd|lainnya|'
        'tak_diketahui", "has_control": true/false/null, "n": bilangan/null, "population": "≤8 kata", '
        '"outcome": "motivasi|hasil_belajar|persepsi|lainnya|tak_diketahui", '
        '"key_result": "angka/statistik utama DISALIN PERSIS dari teks, pisahkan dengan ; (kosong bila tak ada)", '
        '"limitations": "keterbatasan ≤25 kata (dari teks atau dari desainnya)", "confidence": "rendah|sedang|tinggi"}\n'
        "pre_post = pra-pascates SATU kelompok tanpa kontrol. Bedakan hasil belajar vs motivasi vs persepsi.\n"
        f"Petunjuk regex (otomatis, bisa salah): {hint_txt}\n"
        f"{SOURCE_MARK}\nJudul: {ref.title} ({ref.year})\nAbstrak: {abstract or '-'}\n"
        f"Potongan isi: {passage or '-'}\n"
    )


def mock_llm_response(prompt: str) -> str:
    """Jawaban LLM dummy deterministik untuk mode uji: kartu heuristik dari bagian sumber pada prompt."""
    src = prompt.split(SOURCE_MARK, 1)[-1]
    c = heuristic_card("mock", src)
    return json.dumps({"design": c.design, "has_control": c.has_control, "n": c.n, "population": c.population,
                       "outcome": c.outcome, "key_result": c.key_result,
                       "limitations": "kartu uji (mode mock)", "confidence": "sedang"}, ensure_ascii=False)


def _passage_for(store, idx: int, ref) -> str:
    """<=1.500 karakter full-text paling relevan untuk metode/sampel/hasil (tanpa menandai chunk 'terpakai')."""
    if store is None or idx not in getattr(store, "texts", {}):
        return ""
    try:
        parts = store.passages(idx, ref, PASSAGE_QUERY, PASSAGE_CHARS, mark_used=False)
    except Exception:  # noqa: BLE001  (full-text hanya pelengkap)
        return ""
    return " ".join(parts)[:PASSAGE_CHARS]


def extract_card(ref, passages, llm_call: Callable[[str], str] | None, budget: Budget | None,
                 ref_key: str | None = None, is_fatal: Callable[[Exception], bool] | None = None,
                 report: dict | None = None) -> EvidenceCard:
    """Kartu bukti untuk satu referensi. `passages`: str atau list potongan full-text (boleh kosong).

    `llm_call(prompt) -> str`; None = tanpa LLM (kartu heuristik). Galat fatal (`is_fatal`) dilempar, galat lain
    jatuh ke kartu heuristik.
    """
    key = ref_key or ref_key_of(ref)
    passage = " ".join(passages) if isinstance(passages, (list, tuple)) else (passages or "")
    passage = passage[:PASSAGE_CHARS]
    abstract = (getattr(ref, "excerpt", None) or "")[:ABSTRACT_CHARS]
    basis = "fulltext" if passage.strip() else "abstrak"
    source = f"{ref.title}\n{abstract}\n{passage}"
    report = report if report is not None else {}

    def fallback(reason: str) -> EvidenceCard:
        report[reason] = report.get(reason, 0) + 1
        return heuristic_card(key, source, basis)

    if llm_call is None or not (abstract.strip() or passage.strip()):
        return fallback("heuristic")
    prompt = build_prompt(ref, abstract, passage)
    est = estimate_tokens(prompt) + OUT_RESERVE
    if budget is not None and not budget.reserve(est):
        return fallback("budget_skipped")
    out = ""
    try:
        out = str(llm_call(prompt) or "")
    except Exception as e:
        if is_fatal and is_fatal(e):
            raise
        return fallback("failed")
    finally:
        if budget is not None:
            budget.settle(est, estimate_tokens(prompt) + estimate_tokens(out))
    card = card_from_llm(out, key, source, basis)
    if card is None:
        return fallback("failed")
    report["llm"] = report.get("llm", 0) + 1
    report.setdefault("_from_llm", set()).add(key)
    return card


def build_cards(state, fulltext_store, llm_call: Callable[[str], str] | None, budget: Budget | None,
                cache: KVCache | None = None, is_fatal: Callable[[Exception], bool] | None = None,
                report: dict | None = None, workers: int = 4) -> dict[str, EvidenceCard]:
    """Kartu untuk semua `state.daftar_pustaka` yang belum punya kartu di `state.evidence` (paralel, 4 thread).

    Mengembalikan kartu BARU {ref_key: EvidenceCard}. `report` (opsional) diisi hitungan: cached, llm, heuristic,
    budget_skipped, failed. Hanya kartu hasil LLM yang disimpan ke cache (kartu heuristik bisa diperbaiki nanti).
    """
    report = report if report is not None else {}
    existing = set(getattr(state, "evidence", {}) or {})
    jobs, seen = [], set(existing)
    for i, ref in enumerate(state.daftar_pustaka):
        key = ref_key_of(ref)
        if key in seen:
            continue
        seen.add(key)
        jobs.append((i, ref, key))

    out: dict[str, EvidenceCard] = {}
    todo = []
    for i, ref, key in jobs:
        hit = cache.get(CACHE_NS, key) if cache is not None else None
        if isinstance(hit, dict):
            try:
                out[key] = _enforce(EvidenceCard.model_validate({**hit, "ref_key": key}))
                report["cached"] = report.get("cached", 0) + 1
                continue
            except ValueError:
                pass
        todo.append((i, ref, key))

    def one(job):
        i, ref, key = job
        return key, extract_card(ref, _passage_for(fulltext_store, i, ref), llm_call, budget, key, is_fatal, report)

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(one, todo))
        from_llm = report.pop("_from_llm", set())
        for key, card in results:
            out[key] = card
            if cache is not None and key in from_llm:
                cache.set(CACHE_NS, key, card.model_dump())
    report.pop("_from_llm", None)
    return out


def card_brief(card: EvidenceCard) -> dict:
    """Kartu ringkas untuk prompt penulis (±40-60 token)."""
    return {
        "desain": DESIGN_LABEL.get(card.design, card.design),
        "n": card.n if card.n is not None else "-",
        "populasi": card.population or "-",
        "outcome": OUTCOME_LABEL.get(card.outcome, card.outcome),
        "hasil_utama": card.key_result or "-",
        "keterbatasan": card.limitations or "-",
        "boleh_kausal": "ya" if card.causal_ok else "tidak",
    }
