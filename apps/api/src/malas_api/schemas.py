"""Model respons API. Sumber tunggal kontrak untuk OpenAPI (-> packages/api-types) dan penyaring keluaran:
field yang tidak tercantum di sini TIDAK PERNAH sampai ke klien (mis. owner, template_path)."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

JobStatus = Literal["queued", "running", "done", "error", "interrupted", "cancelled"]
StepStatus = Literal["pending", "running", "done", "skipped", "error"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ResumeInfo(_Out):
    available: bool
    done: int
    total: int


class Progress(_Out):
    done: int
    total: int


class JobSummary(_Out):
    id: str
    status: JobStatus
    title: str
    created_at: str
    finished_at: str | None = None
    mock: bool
    byok: bool = False
    has_file: bool
    resume: ResumeInfo | None = None
    mata_kuliah: str | None = None
    progress: Progress | None = None
    current_step: str | None = None
    current_detail: str = ""
    queue_position: int | None = None


class JobStep(_Out):
    status: StepStatus
    detail: str = ""
    started_at: str | None = None
    finished_at: str | None = None


class LogLine(_Out):
    t: str
    msg: str


class JobModels(_Out):
    planner: str
    writer: str


class JobUsage(_Out):
    calls: int = 0
    prompt: int = 0
    completion: int = 0
    total: int = 0


class JobStats(_Out):
    subbab_count: int | None = None
    refs_found: int | None = None
    fulltext_ok: int | None = None
    fulltext_total: int | None = None
    citations_total: int | None = None
    citations_invalid_before: int | None = None
    citations_invalid_after: int | None = None
    citations_suspect: int | None = None  # sitasi-mirip yang tak bisa diurai (wajib diperiksa manual)
    refs_final: int | None = None
    refs_pruned: int | None = None
    refs_pruned_titles: list[str] | None = None  # judul referensi yang dibuang karena tak dikutip


class Penyusun(_Out):
    nama: str
    nim: str


class PaperRequest(_Out):
    judul: str
    mata_kuliah: str
    dosen_pengampu: str
    penyusun: list[Penyusun]
    kelas: str
    universitas: str
    fakultas: str
    jurusan: str
    kota: str
    tahun: str
    subjek: str = ""
    jenjang: str = ""
    jenis_makalah: str = "kajian_pustaka"


class JobOut(_Out):
    id: str
    status: JobStatus
    title: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    mock: bool
    byok: bool = False
    has_file: bool
    key_source: Literal["saved", "session"] | None = None
    provider: str | None = None
    models: JobModels | None = None
    resume_from: str | None = None
    resume: ResumeInfo | None = None
    template: str | None = None
    request: PaperRequest | None = None
    steps: dict[str, JobStep]
    log: list[LogLine] = []
    error: str | None = None
    error_step: str | None = None
    usage: JobUsage | None = None
    stats: JobStats | None = None
    quota_day: str | None = None
    use_logo: bool | None = None
    auto_resumed: bool | None = None
    queue_position: int | None = None


class ProviderInfo(_Out):
    id: str
    label: str
    enabled: bool
    key_url: str
    models: list[str]
    default_planner: str | None = None
    default_writer: str | None = None
    needs_model: bool


class StepInfo(_Out):
    key: str
    label: str
    hint: str


class AuthInfo(_Out):
    mode: Literal["clerk", "anonymous"]
    required: bool


class ConfigOut(_Out):
    hosted: bool
    server_key_available: bool
    models: dict[str, Any] | None = None
    api_key_ok: bool
    mock_default: bool
    fulltext: bool
    providers: list[ProviderInfo]
    templates: list[str]
    default_template: str
    steps: list[StepInfo]
    active_job: str | None = None
    auth: AuthInfo
    daily_quota: int | None = None
    key_storage: bool
    retention_hours: float | None = None
    year: int


class Quota(_Out):
    limit: int
    used: int
    remaining: int
    resets_at: str


class LogoOut(_Out):
    size: int
    updated_at: str | None = None


class MeOut(_Out):
    id: str | None = None
    mode: Literal["clerk", "anonymous"]
    quota: Quota | None = None
    logo: LogoOut | None = None


class SavedKey(_Out):
    provider: str
    saved_at: str | None = None


class KeysOut(_Out):
    enabled: bool
    keys: list[SavedKey]


class ResultOut(_Out):
    result: str
