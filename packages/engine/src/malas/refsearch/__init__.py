"""Pencarian referensi deterministik (kode biasa + API gratis), pengganti agen LLM bertool.

Aktifkan dengan MALAS_REFSEARCH=1. Verifikasi di mesin ber-internet: `python -m malas.refsearch`.
"""
import os
from pathlib import Path
from typing import Optional

from malas.refsearch.http import HttpClient
from malas.refsearch.models import Candidate, SectionQuery
from malas.refsearch.orchestrator import search_references
from malas.refsearch.plan import heuristic_plan, llm_plan

REFSEARCH_CACHE = Path(os.getenv("MALAS_REFSEARCH_CACHE", ".cache/refsearch"))

__all__ = [
    "Candidate",
    "HttpClient",
    "SectionQuery",
    "enabled",
    "heuristic_plan",
    "llm_plan",
    "make_client",
    "search_references",
]


def enabled() -> bool:
    return os.getenv("MALAS_REFSEARCH", "").strip().lower() in {"1", "true", "yes", "on"}


def make_client(session=None, cache_dir: Optional[Path] = REFSEARCH_CACHE) -> HttpClient:
    return HttpClient(session=session, cache_dir=cache_dir, contact=os.getenv("MALAS_CONTACT_EMAIL") or None)
