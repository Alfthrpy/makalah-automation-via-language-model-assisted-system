"""Konfigurasi runtime MALAS, dibaca dari environment variable (.env)."""
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()  # muat .env dari working directory sebelum env dibaca

# Model default; ganti lewat env tanpa menyentuh kode, contoh:
#   MALAS_MODEL=gemini/gemini-2.5-flash
#   MALAS_MODEL=openrouter/deepseek/deepseek-v3.2
# Peran: planner, writer, reviewer (MALAS_MODEL_<PERAN> menimpa MALAS_MODEL).
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
ROLES = ("planner", "writer", "reviewer")

# Prefix model litellm -> env var API key yang dikenali (salah satu cukup)
_KEY_ENV: Dict[str, List[str]] = {
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "groq": ["GROQ_API_KEY"],
}

# Override proses-lebar (dipakai web UI yang menjalankan satu job pada satu waktu).
_mock_override: Optional[bool] = None


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
