"""Brankas API key di memori + redaksi.

Aturan: key pengguna HANYA hidup di memori proses selama job berjalan. Tidak pernah ditulis ke
disk (job.json, cache, log), env, URL, atau penyimpanan browser. Semua teks yang bisa keluar
(error, log Python, traceback) dibersihkan lewat `redact()`.
"""
import io
import logging
import re
import threading
from typing import Dict, Optional

REDACTED = "[KEY-DISEMBUNYIKAN]"
# Pertahanan berlapis: pola bentuk key umum (sk-..., sk-or-v1-...), bila ikut bocor dari penyedia.
_KEY_SHAPES = re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{12,}\b")


class Vault:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: Dict[str, str] = {}

    def put(self, job_id: str, key: str) -> None:
        with self._lock:
            self._keys[job_id] = key

    def pop(self, job_id: str) -> Optional[str]:
        with self._lock:
            return self._keys.pop(job_id, None)

    def discard(self, job_id: str) -> None:
        self.pop(job_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._keys)

    def redact(self, text: str) -> str:
        with self._lock:
            keys = [k for k in self._keys.values() if k]
        for k in keys:
            text = text.replace(k, REDACTED)
        return _KEY_SHAPES.sub(REDACTED, text)


_active: Optional[Vault] = None
_factory_installed = False


def install_log_redaction(vault: Vault) -> None:
    """Semua record logging Python (termasuk litellm/uvicorn) dibersihkan sebelum diteruskan."""
    global _active, _factory_installed
    _active = vault
    if _factory_installed:
        return
    base = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = base(*args, **kwargs)
        v = _active
        if v is not None:
            try:
                record.msg = v.redact(record.getMessage())
                record.args = ()
            except Exception:  # noqa: BLE001 - logging tidak boleh melempar
                pass
        return record

    logging.setLogRecordFactory(factory)
    _factory_installed = True


class Sink(io.TextIOBase):
    """Pengganti stdout/stderr yang membuang semua tulisan (mode hosting: tanpa jejak di log host).

    Subclass TextIOBase agar library yang memeriksa `.encoding`, `.isatty()`, `.reconfigure()` dll.
    (CrewAI, rich, main.py) tetap bekerja.
    """

    encoding = "utf-8"
    errors = "replace"

    def write(self, s: str) -> int:
        return len(s)

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def reconfigure(self, **_kwargs) -> None:
        pass
