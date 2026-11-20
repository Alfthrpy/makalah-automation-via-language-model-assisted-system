"""Penyedia LLM yang boleh dipakai pengguna dengan API key sendiri (BYOK).

Base URL dikunci di sisi server (bukan input pengguna) supaya API key tidak bisa diarahkan
ke host sembarangan (SSRF / pencurian key). Env hanya bisa diatur operator server.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    model_prefix: str  # awalan model crewAI 1.x (provider native: openrouter/ -> OpenAI-compatible, openai/ + base_url)
    key_url: str  # halaman resmi pembuatan key (tautan bantuan di UI)
    models: Tuple[str, ...] = ()  # saran di UI; pengguna tetap boleh mengetik model lain
    default_planner: str = ""
    default_writer: str = ""
    base_url_env: Optional[str] = None  # env yang menyimpan base URL (bila bukan default penyedia)
    fixed_base_url: Optional[str] = None

    @property
    def base_url(self) -> Optional[str]:
        """Env (jika diisi & https valid) menimpa nilai tetap. Pengguna web tidak bisa mengubahnya."""
        if self.base_url_env:
            url = (os.getenv(self.base_url_env) or "").strip().rstrip("/")
            if _valid_https(url):
                return url
        return self.fixed_base_url

    @property
    def enabled(self) -> bool:
        return True

    @property
    def needs_model(self) -> bool:
        return not (self.default_planner and self.default_writer)


def _valid_https(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password


PROVIDERS: Dict[str, Provider] = {
    "openrouter": Provider(
        id="openrouter",
        label="OpenRouter",
        model_prefix="openrouter/",
        key_url="https://openrouter.ai/keys",
        models=(
            "deepseek/deepseek-v3.2",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "openai/gpt-5-mini",
            "anthropic/claude-haiku-4.5",
        ),
        default_planner="deepseek/deepseek-v3.2",
        default_writer="google/gemini-2.5-flash",
    ),
    # API Kenari kompatibel OpenAI (https://kenari.id/en/docs/chat): base URL https://kenari.id/v1,
    # key berawalan "kn-", dikirim sebagai "Authorization: Bearer". Model gratis berakhiran ":free".
    # Katalog model lengkap ada di halaman "Models and pricing" Kenari; pengguna mengetik id modelnya.
    "kenari": Provider(
        id="kenari",
        label="Kenari",
        model_prefix="openai/",
        key_url="https://kenari.id/en/docs/authentication",
        models=("step-3-7-flash:free",),
        fixed_base_url="https://kenari.id/v1",
        base_url_env="MALAS_KENARI_BASE_URL",  # opsional: timpa (harus https)
    ),
}


def get_provider(provider_id: str) -> Optional[Provider]:
    return PROVIDERS.get(provider_id)


def public_info() -> list:
    """Info provider untuk UI (tanpa base URL)."""
    return [
        {
            "id": p.id, "label": p.label, "enabled": p.enabled, "key_url": p.key_url,
            "models": list(p.models), "default_planner": p.default_planner,
            "default_writer": p.default_writer, "needs_model": p.needs_model,
        }
        for p in PROVIDERS.values()
    ]
