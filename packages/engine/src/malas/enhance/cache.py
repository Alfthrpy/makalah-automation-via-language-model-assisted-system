"""Cache key-value sqlite kecil untuk Enhancing Engine (kartu bukti).

ATURAN DATA (HANDOFF §9, docs/enhancing-engine.md §0 poin 5): cache ini bisa dipakai lintas pengguna, jadi HANYA boleh
berisi data turunan sumber PUBLIK dengan kunci DOI/hash judul+tahun (mis. kartu bukti dari abstrak/teks paper).
JANGAN pernah menyimpan teks makalah pengguna, input pengguna, atau key di sini.

Lokasi: `.cache/enhance/enhance.sqlite3` (folder ditimpa env `MALAS_ENHANCE_CACHE`). TTL bawaan 90 hari.
Gagal membuka/menulis cache = cache nonaktif tanpa error (cache hanya optimasi).
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path(".cache/enhance")
TTL_DAYS = 90


def default_dir() -> Path:
    return Path(os.getenv("MALAS_ENHANCE_CACHE") or DEFAULT_DIR)


class KVCache:
    """Tabel `kv(ns, key, value JSON, ts)`; thread-safe (satu koneksi + kunci)."""

    def __init__(self, folder: Path | None = None, ttl_days: float = TTL_DAYS):
        self.ttl = ttl_days * 86400
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None
        try:
            folder = Path(folder) if folder is not None else default_dir()
            folder.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(str(folder / "enhance.sqlite3"), check_same_thread=False, timeout=5)
            db.execute("CREATE TABLE IF NOT EXISTS kv (ns TEXT, key TEXT, value TEXT, ts REAL, PRIMARY KEY (ns, key))")
            db.commit()
            self._db = db
        except (OSError, sqlite3.Error):
            self._db = None  # nonaktif

    @property
    def enabled(self) -> bool:
        return self._db is not None

    def get(self, ns: str, key: str) -> Any | None:
        if self._db is None:
            return None
        try:
            with self._lock:
                row = self._db.execute("SELECT value, ts FROM kv WHERE ns=? AND key=?", (ns, key)).fetchone()
            if not row or time.time() - row[1] > self.ttl:
                return None
            return json.loads(row[0])
        except (sqlite3.Error, ValueError):
            return None

    def set(self, ns: str, key: str, value: Any) -> None:
        if self._db is None:
            return
        try:
            data = json.dumps(value, ensure_ascii=False)
            with self._lock:
                self._db.execute("INSERT OR REPLACE INTO kv (ns, key, value, ts) VALUES (?, ?, ?, ?)",
                                 (ns, key, data, time.time()))
                self._db.commit()
        except (sqlite3.Error, TypeError, ValueError):
            pass

    def close(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
            except sqlite3.Error:
                pass
            self._db = None
