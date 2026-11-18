"""Konfigurasi runtime MALAS, dibaca dari environment variable (.env)."""
import os

from crewai import LLM

# Model default; ganti lewat env tanpa menyentuh kode, contoh:
#   MALAS_MODEL=gemini/gemini-2.5-flash
#   MALAS_MODEL=anthropic/claude-sonnet-5-5
DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_llm(role: str = "default"):
    """LLM untuk sebuah peran.

    Urutan: MALAS_MODEL_<ROLE> -> MALAS_MODEL -> DEFAULT_MODEL.
    MALAS_MOCK=1 memakai AutoFakeLLM (tanpa API call) untuk uji alur.
    """
    if _flag("MALAS_MOCK"):
        from malas.mock.mock_llm import AutoFakeLLM

        return AutoFakeLLM(model_name="mock")

    model = (
        os.getenv(f"MALAS_MODEL_{role.upper()}")
        or os.getenv("MALAS_MODEL")
        or DEFAULT_MODEL
    )
    return LLM(model=model)
