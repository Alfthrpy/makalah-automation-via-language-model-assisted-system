"""Rencana query per sub-bab. Heuristik murni kode; opsional diperkaya SATU panggilan LLM murah."""
import json
import re
from typing import Callable, Dict, List, Optional

from malas.refsearch.models import SectionQuery

BIDANG = ("medis", "teknik", "sains", "sosial", "hukum", "agama", "ekonomi", "humaniora", "pendidikan", "umum")

# Judul sub-bab generik tidak membawa topik: dibuang dari query, topik diambil dari judul makalah.
_GENERIC = re.compile(
    r"\b(latar belakang|pendahuluan|pembahasan|landasan teori|tinjauan pustaka|kajian teori|analisis|interpretasi|"
    r"data|informasi|studi kasus|contoh|implikasi|penelitian|tantangan|keterbatasan|potensi|lanjutan|kesimpulan|"
    r"saran|tujuan|penulisan|rumusan masalah|dan|serta|atau|di|ke|dari|yang|untuk)\b", re.I)
_ID_HINT = re.compile(r"\b(dan|yang|di|untuk|pada|dalam|terhadap|dengan|oleh|sebagai|indonesia|nasional|daerah|"
                      r"islam|hukum|pancasila|undang)\b", re.I)


def strip_number(section: str) -> str:
    return re.sub(r"^\s*(?:bab\s+)?[\dIVX]+(?:\.\d+)*[.)]?\s*", "", section, flags=re.I).strip()


def heuristic_plan(judul: str, sections: List[str]) -> List[SectionQuery]:
    indo = len(_ID_HINT.findall(judul)) >= 1
    out = []
    for s in sections:
        sub = " ".join(_GENERIC.sub(" ", strip_number(s)).split())
        q = " ".join(f"{judul} {sub}".split())
        out.append(SectionQuery(section=s, q_en="", q_id=q, bidang="umum", indo=indo))
    return out


def _prompt(judul: str, mata_kuliah: str, sections: List[str]) -> str:
    listing = "\n".join(f"- {s}" for s in sections)
    return (
        "Anda membantu mencari literatur akademik untuk sebuah makalah mahasiswa Indonesia.\n"
        f'Judul makalah: "{judul}"\nMata kuliah: "{mata_kuliah}"\nSub-bab yang butuh referensi:\n{listing}\n\n'
        "Untuk SETIAP sub-bab buat query pencarian jurnal. Jawab HANYA JSON valid (tanpa teks lain) berbentuk:\n"
        '{"<judul sub-bab persis seperti di atas>": {"q_en": "<=8 kata kunci bahasa Inggris", '
        '"q_id": "<=8 kata kunci bahasa Indonesia", '
        f'"bidang": "salah satu dari {"|".join(BIDANG)}", "indo": true jika topik spesifik Indonesia (hukum/budaya/kebijakan/'
        "sejarah/agama lokal) selain itu false}}\n"
        "Query harus spesifik pada topik sub-bab DAN judul makalah, bukan kata generik seperti 'latar belakang'."
    )


def _parse_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def llm_plan(judul: str, mata_kuliah: str, sections: List[str], call: Callable[[str], str]) -> List[SectionQuery]:
    """Satu panggilan LLM -> query EN+ID per sub-bab. Gagal/tak lengkap -> bagian itu jatuh ke heuristik."""
    base = heuristic_plan(judul, sections)
    try:
        prompt = _prompt(judul, mata_kuliah, sections)
        data = _parse_json(call(prompt)) or {}
    except Exception:
        return base
    norm: Dict[str, dict] = {strip_number(k).lower(): v for k, v in data.items() if isinstance(v, dict)}
    out = []
    for sq in base:
        d = norm.get(strip_number(sq.section).lower()) or {}
        q_en, q_id = str(d.get("q_en") or "").strip(), str(d.get("q_id") or "").strip()
        bidang = str(d.get("bidang") or "").lower()
        out.append(SectionQuery(
            section=sq.section,
            q_en=q_en[:120],
            q_id=(q_id or sq.q_id)[:120],
            bidang=bidang if bidang in BIDANG else sq.bidang,
            indo=bool(d["indo"]) if isinstance(d.get("indo"), bool) else sq.indo,
        ))
    return out
