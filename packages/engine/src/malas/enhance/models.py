"""Model data Enhancing Engine (docs/enhancing-engine.md §6.3). Hanya pydantic: aman diimpor dari mana saja."""
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["blocker", "major", "minor", "info"]
FixKind = Literal["auto", "patch", "human", "none"]
SEVERITY_WEIGHT: dict[str, int] = {"blocker": 8, "major": 3, "minor": 1, "info": 0}


class Location(BaseModel):
    bab: str | None = None  # kunci Bab ("I", "II", ...)
    subbab: str | None = None  # judul sub-bab apa adanya (kunci stabil, termasuk nomor)
    paragraph: int | None = None  # indeks item konten


class Finding(BaseModel):
    rule_id: str  # "CIT-001"
    severity: Severity
    where: Location = Field(default_factory=Location)
    message: str  # Indonesia, <=200 karakter, tanpa klaim absolut
    evidence: str = ""  # kutipan <=200 karakter dari teks
    fix: FixKind = "none"
    hint: str = ""  # instruksi singkat untuk penambal LLM
    source: Literal["lint", "critic", "verifier"] = "lint"


def score_findings(findings: list[Finding]) -> int:
    """Skor berbobot (blocker=8, major=3, minor=1): dasar penerimaan monoton tambalan."""
    return sum(SEVERITY_WEIGHT[f.severity] for f in findings)


class EvidenceCard(BaseModel):
    """Ringkasan terstruktur satu referensi (kunci cache = doi atau hash judul+tahun)."""

    ref_key: str
    design: Literal["rct", "kuasi_eksperimen", "pre_post", "survei", "kualitatif", "slr", "konseptual",
                    "pengembangan_rnd", "lainnya", "tak_diketahui"] = "tak_diketahui"
    has_control: bool | None = None
    n: int | None = None
    population: str = ""  # "siswa MTs", "mahasiswa", ...
    outcome: Literal["motivasi", "hasil_belajar", "persepsi", "lainnya", "tak_diketahui"] = "tak_diketahui"
    key_result: str = ""  # angka VERBATIM dari sumber
    limitations: str = ""
    causal_ok: bool = False  # True hanya bila desain mendukung klaim kausal (rct / kuasi dengan kontrol)
    confidence: Literal["rendah", "sedang", "tinggi"] = "rendah"
    basis: Literal["abstrak", "fulltext"] = "abstrak"


class Scope(BaseModel):
    jenis_makalah: str = "kajian_pustaka"  # kajian_pustaka | penelitian
    subjek: str = ""  # mis. "siswa MTs"
    jenjang: str = ""


class Blueprint(BaseModel):
    """Kerangka argumen (1 panggilan planner); disimpan di Makalah.blueprint."""

    scope: Scope = Field(default_factory=Scope)
    research_questions: list[str] = Field(default_factory=list)  # <=3 kalimat tanya utuh
    rq_map: dict[str, list[str]] = Field(default_factory=dict)  # RM -> judul sub-bab yang menjawab
    subbab_tasks: dict[str, str] = Field(default_factory=dict)  # judul sub-bab -> tugas argumen
    domain_checklist: list[str] = Field(default_factory=list)  # 3-6 istilah/contoh wajib
    avoid_repeat: list[str] = Field(default_factory=list)


class ContextPack(BaseModel):
    """Konteks penulis per sub-bab, dibangun KODE (bukan LLM)."""

    outline_titles: list[str] = Field(default_factory=list)
    rq: list[str] = Field(default_factory=list)
    ledger: list[str] = Field(default_factory=list)  # ringkasan ekstraktif yang SUDAH dipakai
    digest_bab2: list[str] = Field(default_factory=list)  # hanya untuk Kesimpulan
