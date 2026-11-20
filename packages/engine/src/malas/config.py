"""Konfigurasi runtime MALAS, dibaca dari environment variable (.env)."""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()  # muat .env dari working directory sebelum env dibaca

# Matikan telemetry/tracing CrewAI SEBELUM crewai diimpor dari jalur mana pun (CLI, web, tes):
# tanpa ini data pemakaian dikirim keluar dan ada error koneksi berisik saat offline.
for _k, _v in (("OTEL_SDK_DISABLED", "true"), ("CREWAI_DISABLE_TELEMETRY", "true"),
               ("CREWAI_DISABLE_TRACKING", "true"), ("CREWAI_TRACING_ENABLED", "false")):
    os.environ.setdefault(_k, _v)

# Model default; ganti lewat env tanpa menyentuh kode, contoh:
#   MALAS_MODEL=gemini/gemini-2.5-flash
#   MALAS_MODEL=openrouter/deepseek/deepseek-v3.2
# Peran: planner, writer, reviewer (MALAS_MODEL_<PERAN> menimpa MALAS_MODEL).
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
ROLES = ("planner", "writer", "reviewer")

# Prefix model crewAI -> env var API key yang dikenali (salah satu cukup)
_KEY_ENV: Dict[str, List[str]] = {
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "groq": ["GROQ_API_KEY"],
}

# Override proses-lebar (dipakai web UI yang menjalankan satu job pada satu waktu).
_mock_override: Optional[bool] = None


@dataclass
class Runtime:
    """Kredensial milik pengguna untuk SATU job (BYOK). Hanya ada di memori; key tidak ikut repr."""

    provider_id: str
    api_key: str = field(repr=False)
    planner_model: str
    writer_model: str

    def model_for(self, role: str) -> str:
        return self.planner_model if role == "planner" else self.writer_model  # reviewer memakai model penulis


_runtime: Optional[Runtime] = None


def set_runtime(rt: Optional[Runtime]) -> None:
    """Pasang/lepas kredensial job. Web UI hanya menjalankan satu job pada satu waktu."""
    global _runtime
    _runtime = rt


def set_mock_override(value: Optional[bool]) -> None:
    """True/False memaksa mode mock; None kembali ke env MALAS_MOCK."""
    global _mock_override
    _mock_override = value


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_mock() -> bool:
    return _mock_override if _mock_override is not None else _flag("MALAS_MOCK")


def model_for(role: str = "default") -> str:
    """Urutan: MALAS_MODEL_<ROLE> -> MALAS_MODEL -> DEFAULT_MODEL."""
    return os.getenv(f"MALAS_MODEL_{role.upper()}") or os.getenv("MALAS_MODEL") or DEFAULT_MODEL


def get_llm(role: str = "default"):
    """LLM untuk sebuah peran. Mode mock memakai AutoFakeLLM (tanpa API call)."""
    if is_mock():
        from malas.mock.mock_llm import AutoFakeLLM

        return AutoFakeLLM(model_name="mock")

    from crewai import LLM

    if _runtime is not None:
        from malas.providers import get_provider

        prov = get_provider(_runtime.provider_id)
        if prov is None or not prov.enabled:
            raise RuntimeError("Penyedia model tidak tersedia")
        return LLM(
            model=prov.model_prefix + _runtime.model_for(role),
            api_key=_runtime.api_key,
            base_url=prov.base_url,
        )
    return LLM(model=model_for(role))


def _key_present(model: str) -> bool:
    envs = _KEY_ENV.get(model.split("/", 1)[0])
    return True if envs is None else any(os.getenv(e) for e in envs)  # provider tak dikenal: jangan menuduh


def describe() -> dict:
    """Ringkasan konfigurasi untuk UI (tanpa membocorkan nilai secret)."""
    models = {r: model_for(r) for r in ROLES}
    return {
        "models": models,
        "api_key_ok": all(_key_present(m) for m in models.values()),
        "mock_default": _flag("MALAS_MOCK"),
        "fulltext": os.getenv("MALAS_FULLTEXT", "1") != "0",
    }


# --- Enhancing Engine (docs/enhancing-engine.md §6.5) -------------------------------------
ENHANCE_TIERS = ("off", "lite", "standard", "deep")


_enhance_override: Optional[str] = None


def set_enhance_override(value: Optional[str]) -> None:
    """Tier untuk SATU job (web memilih per job; satu job pada satu waktu). None = kembali ke env MALAS_ENHANCE."""
    global _enhance_override
    _enhance_override = value if value in ENHANCE_TIERS else None


def enhance_max() -> str:
    """Batas atas tier yang boleh dipilih pengguna (operator: MALAS_ENHANCE_MAX, default deep)."""
    v = os.getenv("MALAS_ENHANCE_MAX", "deep").strip().lower()
    return v if v in ENHANCE_TIERS else "deep"


def clamp_enhance(value: str) -> str:
    """Tier hasil pilihan pengguna, dipotong ke batas operator."""
    cap = ENHANCE_TIERS.index(enhance_max())
    return ENHANCE_TIERS[min(ENHANCE_TIERS.index(value) if value in ENHANCE_TIERS else 1, cap)]


def enhance_tier() -> str:
    """Tier aktif: override per job, lalu MALAS_ENHANCE=off|lite|standard|deep (default lite: lint + konteks, tanpa LLM baru)."""
    if _enhance_override is not None:
        return _enhance_override
    v = os.getenv("MALAS_ENHANCE", "lite").strip().lower()
    return v if v in ENHANCE_TIERS else "lite"


def enhance_budget() -> int:
    """Batas token tahap LLM enhancing (MALAS_ENHANCE_MAX_TOKENS, default 40000)."""
    try:
        return max(0, int(os.getenv("MALAS_ENHANCE_MAX_TOKENS", "40000")))
    except ValueError:
        return 40000
