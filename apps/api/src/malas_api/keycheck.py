"""Pemeriksaan ringan API key ke penyedia SEBELUM disimpan (hanya menolak yang jelas salah).

Hasil: "valid" | "invalid" | "unknown". Hanya HTTP 401 dianggap "invalid"; segala hal lain (timeout, 5xx, 403 karena
blokir jaringan, endpoint berbeda) = "unknown" dan key tetap boleh disimpan, supaya gangguan penyedia tidak menghalangi
pengguna. URL dikunci di server (bukan input pengguna); redirect dimatikan agar header Authorization tidak ikut diteruskan.
Nonaktifkan dengan MALAS_KEY_VERIFY=0.
"""
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

from malas.providers import get_provider

log = logging.getLogger("malas.keycheck")
TIMEOUT = 5.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: D401
        return None


def _url(provider_id: str) -> Optional[str]:
    prov = get_provider(provider_id)
    if prov is None:
        return None
    if provider_id == "openrouter":
        return "https://openrouter.ai/api/v1/key"
    base = prov.base_url
    return f"{base}/models" if base else None


def _status(url: str, key: str) -> Optional[int]:
    """HTTP status, atau None bila tidak tercapai. Tidak pernah mencatat/menaikkan key."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                                               "User-Agent": "malas-keycheck"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001 - jaringan/TLS/timeout
        return None


def check(provider_id: str, key: str) -> str:
    if os.getenv("MALAS_KEY_VERIFY", "1").strip().lower() in {"0", "false", "no", "off"}:
        return "unknown"
    url = _url(provider_id)
    if not url:
        return "unknown"
    code = _status(url, key)
    if code is None:
        log.info("Pemeriksaan key ke %s tidak tercapai", provider_id)
        return "unknown"
    if 200 <= code < 300:
        return "valid"
    return "invalid" if code == 401 else "unknown"
