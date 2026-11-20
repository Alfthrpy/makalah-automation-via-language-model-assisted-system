"""Klien HTTP untuk pencarian referensi: timeout, retry + backoff, batas laju per host,
circuit breaker per host, dan cache disk (sqlite3 stdlib). Tidak pernah melempar exception ke pemanggil:
bila gagal, mengembalikan None.
"""
import hashlib
import json
import random
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

import requests

# jeda minimum antar request per host (detik), mengikuti ketentuan masing-masing layanan
MIN_INTERVAL: Dict[str, float] = {
    "api.openalex.org": 0.25,
    "api.crossref.org": 0.4,  # polite pool: list 3 rps
    "export.arxiv.org": 3.1,  # ToU arXiv: 1 request / 3 detik
    "www.ebi.ac.uk": 0.2,
    "doaj.org": 0.5,
    "api.unpaywall.org": 0.1,
}
_SECRET_PARAMS = {"api_key", "mailto", "email"}  # tidak ikut kunci cache
MAX_BODY = 2_000_000


class HttpClient:
    def __init__(
        self,
        session: Any = None,
        cache_dir: Optional[Path] = None,
        contact: Optional[str] = None,
        ttl: float = 14 * 86400,
        retries: int = 3,
        timeout: tuple = (5, 15),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        breaker_after: int = 3,
    ):
        self.session = session or requests.Session()
        self.contact = contact
        self.ttl, self.retries, self.timeout = ttl, retries, timeout
        self._sleep, self._clock = sleep, clock
        self._breaker_after = breaker_after
        self._lock = threading.Lock()
        self._host_lock: Dict[str, threading.Lock] = {}
        self._next_ok: Dict[str, float] = {}
        self._fails: Dict[str, int] = {}
        self.calls = 0  # request jaringan sungguhan (bukan cache), untuk pelaporan
        self.cache_hits = 0
        self._db = None
        if cache_dir:
            try:
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                self._db = sqlite3.connect(str(Path(cache_dir) / "refsearch.sqlite"), check_same_thread=False)
                self._db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, t REAL, v TEXT)")
                self._db.commit()
            except (OSError, sqlite3.Error):
                self._db = None

    # ------------------------------------------------------------------ cache
    def _key(self, url: str, params: Optional[dict]) -> str:
        p = sorted((k, str(v)) for k, v in (params or {}).items() if k not in _SECRET_PARAMS)
        return hashlib.sha1(json.dumps([url, p]).encode()).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        if not self._db:
            return None
        try:
            with self._lock:
                row = self._db.execute("SELECT t, v FROM c WHERE k=?", (key,)).fetchone()
            if row and time.time() - row[0] < self.ttl:
                return row[1]
        except sqlite3.Error:
            pass
        return None

    def _cache_put(self, key: str, body: str) -> None:
        if not self._db or len(body) > MAX_BODY:
            return
        try:
            with self._lock:
                self._db.execute("INSERT OR REPLACE INTO c VALUES (?,?,?)", (key, time.time(), body))
                self._db.commit()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------ laju & breaker
    def _throttle(self, host: str) -> None:
        gap = MIN_INTERVAL.get(host, 0.1)
        with self._lock:
            hl = self._host_lock.setdefault(host, threading.Lock())
        with hl:  # serialisasi per host agar jeda benar-benar dihormati antar thread
            wait = self._next_ok.get(host, 0.0) - self._clock()
            if wait > 0:
                self._sleep(wait)
            self._next_ok[host] = self._clock() + gap

    def is_open(self, host: str) -> bool:
        """True bila host dianggap mati (gagal beruntun) -> lewati sisa job."""
        return self._fails.get(host, 0) >= self._breaker_after

    # ------------------------------------------------------------------ inti
    def get_text(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[str]:
        host = urlparse(url).netloc
        key = self._key(url, params)
        cached = self._cache_get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        if self.is_open(host):
            return None
        hdrs = {"User-Agent": f"malas-refsearch/0.1 (mailto:{self.contact})" if self.contact else "malas-refsearch/0.1"}
        hdrs.update(headers or {})
        for attempt in range(self.retries):
            self._throttle(host)
            self.calls += 1
            try:
                r = self.session.get(url, params=params, headers=hdrs, timeout=self.timeout)
            except Exception:
                r = None
            code = getattr(r, "status_code", 0)
            if r is not None and 200 <= code < 300:
                self._fails[host] = 0
                self._cache_put(key, r.text)
                return r.text
            if r is not None and code in (400, 401, 403, 404, 422):
                if code in (401, 403):  # key salah / diblokir: percuma diulang
                    self._fails[host] = self._breaker_after
                return None
            # 429 / 5xx / galat jaringan -> backoff
            delay = 0.5 * (2 ** attempt) + random.random() * 0.3
            ra = (getattr(r, "headers", None) or {}).get("Retry-After")
            if ra:
                try:
                    delay = max(delay, min(float(ra), 10.0))
                except ValueError:
                    pass
            if attempt < self.retries - 1:
                self._sleep(delay)
        self._fails[host] = self._fails.get(host, 0) + 1
        return None

    def get_json(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[dict]:
        text = self.get_text(url, params, headers)
        if text is None:
            return None
        try:
            data = json.loads(text)
            return data if isinstance(data, (dict, list)) else None
        except ValueError:
            return None
