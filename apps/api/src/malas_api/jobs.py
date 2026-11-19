"""Manajemen job pembuatan makalah.

- Status, progres, checkpoint, dan hasil .docx disimpan di database (Neon Postgres di produksi; SQLite untuk
  lokal/tes), jadi selamat dari restart/tidur host. Disk hanya dipakai sebagai folder kerja sementara.
- Antrean = baris `jobs` berstatus `queued`; satu pekerja mengambilnya (FIFO) dengan claim atomik
  (`FOR UPDATE SKIP LOCKED` di Postgres). Pekerja mengirim heartbeat; job `running` yang heartbeat-nya basi
  (proses mati) ditandai `interrupted` dan, bila key tersimpan, otomatis dilanjutkan dari checkpoint.
- API key pengguna (BYOK) TIDAK PERNAH masuk job dict / database dalam bentuk polos. Dua jalur:
    session  key hanya di `Vault` (memori), dibuang pada semua jalur akhir.
    saved    pengguna memilih menyimpan: terenkripsi (Fernet) di tabel `user_api_keys`; didekripsi hanya
             saat job mulai, lalu masuk Vault (agar ikut disaring dari log/error).
- Setiap job punya pemilik (id eksternal); job orang lain tidak terlihat.
- `runner` bisa disuntik, jadi API dapat diuji tanpa menjalankan CrewAI.
"""
import contextlib
import logging
import re
import shutil
import tempfile
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from malas import checkpoint
from malas.config import Runtime
from malas.steps import STEP_KEYS
from malas_api import db as dbmod
from malas_api.crypto import CryptoError, KeyCipher
from malas_api.repo import Repo
from malas_api.storage import DbStorage, Storage
from malas_api.vault import Sink, Vault, install_log_redaction

log = logging.getLogger("malas.jobs")

ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_LOG = 300
ACTIVE = {"queued", "running"}

# runner(job_dict, progress_cb, output_path, runtime_or_None) -> {"usage": {...}, "stats": {...}}
Runner = Callable[[dict, Callable[[str, str, str], None], Path, Optional[Runtime]], dict]


class UserFacingError(Exception):
    """Pesan sudah ramah dan aman; ditampilkan ke pengguna apa adanya (tanpa klasifikasi kata kunci)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_database_url(root: Path) -> str:
    """Tanpa DATABASE_URL: SQLite di folder output (mode lokal)."""
    return dbmod.sqlite_url(Path(root) / "malas.db")


def default_runner(job: dict, progress: Callable[[str, str, str], None], output_path: Path,
                   runtime: Optional[Runtime]) -> dict:
    """Jalankan MalasFlow sungguhan (impor ditunda: CrewAI berat dan tidak perlu saat server naik)."""
    from malas import config
    from malas.main import MalasFlow

    config.set_mock_override(True if job["mock"] else None)
    config.set_runtime(runtime)
    try:
        flow = MalasFlow()
        flow.input_data = dict(job["request"])
        flow.template_path = job["template_path"]
        flow.output_path = str(output_path)
        flow.progress = progress
        flow.checkpoint_path = Path(output_path).parent / "checkpoint.json"
        flow.resume = bool(job.get("resume_from"))
        flow.kickoff()
        return {"usage": getattr(flow, "usage", {}), "stats": getattr(flow, "stats", {})}
    finally:
        config.set_runtime(None)
        config.set_mock_override(None)


class JobManager:
    def __init__(self, root: Path, runner: Runner = default_runner, *,
                 retention_hours: Optional[float] = None, quiet: bool = False,
                 database_url: Optional[str] = None, migrate_url: Optional[str] = None, storage: Optional[Storage] = None,
                 cipher: Optional[KeyCipher] = None, stale_after: float = 90.0, heartbeat_every: float = 20.0,
                 poll_interval: float = 0.5, auto_resume: bool = True):
        """root: folder kerja sementara (+ lokasi SQLite bila database_url kosong).
        retention_hours: job selesai yang lebih tua dihapus otomatis (None = simpan).
        quiet: buang semua stdout/stderr saat job berjalan (mode hosting: tanpa jejak di log host).
        stale_after: detik tanpa heartbeat sebelum job `running` dianggap mati."""
        self.root = Path(root)
        self.work_dir = self.root / "work"
        shutil.rmtree(self.work_dir, ignore_errors=True)  # sisa job yang proses-nya mati
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.db = dbmod.Database(database_url or default_database_url(self.root), migrate_url=migrate_url)
        self.repo = Repo(self.db)
        self.storage: Storage = storage or DbStorage(self.db.session)
        self.cipher = cipher
        self._runner = runner
        self._retention = retention_hours
        self._quiet = quiet
        self._stale_after = stale_after
        self._heartbeat_every = heartbeat_every
        self._poll = poll_interval
        self._auto_resume = auto_resume
        self.vault = Vault()
        self._pending_runtime: Dict[str, Optional[Runtime]] = {}  # job_id -> kredensial sesi, hanya di memori
        self._lock = threading.Lock()
        install_log_redaction(self.vault)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.purge()
        self.recover_stale()
        self._worker = threading.Thread(target=self._loop, name="malas-worker", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ pemulihan & retensi
    @property
    def key_storage_enabled(self) -> bool:
        return self.cipher is not None

    def _resume_info(self, job_id: str) -> Optional[dict]:
        """Info 'bisa dilanjutkan' dari checkpoint di DB (None bila tidak ada)."""
        meta = self.repo.checkpoint_meta(job_id)
        if not meta:
            return None
        return {"available": bool(meta["outline"]), "done": meta["done"], "total": meta["total"]}

    def recover_stale(self) -> int:
        """Tandai job `running` yang heartbeat-nya basi sebagai `interrupted`; lanjutkan otomatis bila key tersimpan."""
        n = 0
        for jid in self.repo.stale_running(self._stale_after):
            resume = self._resume_info(jid)

            def mark(j: dict) -> None:
                if j["status"] != "running":
                    return
                j["status"], j["error"] = "interrupted", "Server berhenti saat job ini berjalan."
                j["finished_at"], j["resume"] = _now(), resume
                j["_changed"] = True

            job = self.repo.update(jid, mark)
            if not job or not job.pop("_changed", False):
                continue
            n += 1
            self._maybe_auto_resume(job)
        return n

    def _maybe_auto_resume(self, job: dict) -> None:
        resume = job.get("resume") or {}
        if not (self._auto_resume and self.cipher and job.get("key_source") == "saved" and resume.get("available")
                and not job.get("auto_resumed") and not job.get("mock")):
            return
        try:
            self.repo.update(job["id"], lambda j: j.update(auto_resumed=True))
            self.submit(job["request"], False, job["template_path"], job["template"], owner=job["owner"],
                        resume_from=job["id"], key_source="saved", provider=job["provider"], models=job["models"])
        except Exception:  # noqa: BLE001 - pemulihan tidak boleh menjatuhkan server
            log.exception("Gagal melanjutkan otomatis job %s", job["id"])

    def purge(self) -> int:
        """Hapus job selesai yang melewati masa simpan. Dipanggil lazy (tanpa thread latar)."""
        if not self._retention:
            return 0
        old = self.repo.expired(datetime.now(timezone.utc) - timedelta(hours=self._retention))
        for jid in old:
            self.storage.delete(jid)
            self.repo.delete(jid)
        return len(old)

    # ------------------------------------------------------------------ API
    def submit(self, request: dict, mock: bool, template_path: str, template_name: str, *,
               owner: str = "", runtime: Optional[Runtime] = None, resume_from: Optional[str] = None,
               key_source: Optional[str] = None, provider: Optional[str] = None,
               models: Optional[dict] = None) -> dict:
        self.purge()
        if runtime is not None:
            key_source, provider = "session", runtime.provider_id
            models = {"planner": runtime.planner_model, "writer": runtime.writer_model}
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "owner": owner,
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "title": request["judul"],
            "mock": mock,
            "byok": key_source is not None,  # hanya penanda; key TIDAK disimpan di sini
            "key_source": key_source,  # "session" (memori saja) | "saved" (terenkripsi di DB) | None
            "provider": provider,
            "models": models,
            "resume_from": resume_from,  # id job asal bila ini kelanjutan
            "resume": None,  # diisi saat berhenti: {"available", "done", "total"}
            "template": template_name,
            "template_path": template_path,
            "request": request,
            "steps": {k: {"status": "pending", "detail": ""} for k in STEP_KEYS},
            "log": [],
            "error": None,
            "error_step": None,
            "usage": None,
            "stats": None,
            "has_file": False,
        }
        if resume_from and not (self.repo.checkpoint_meta(resume_from)):
            raise ValueError("Checkpoint job asal tidak ditemukan")
        with self._lock:
            if runtime is not None:
                self.vault.put(job_id, runtime.api_key)
                self._pending_runtime[job_id] = runtime  # dipegang HANYA di sini; dibuang saat job mulai
            try:
                self.repo.create_job(job)
                if resume_from and not self.repo.copy_checkpoint(resume_from, job_id):  # job asal tetap utuh
                    self.repo.delete(job_id)
                    raise ValueError("Checkpoint job asal tidak ditemukan")
            except Exception:
                self._discard_secret(job_id)
                raise
        self._wake.set()
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[dict]:
        return self.repo.get(job_id) if ID_RE.match(job_id) else None

    def list(self, owner: Optional[str] = None, limit: int = 30) -> List[dict]:
        self.purge()
        return self.repo.list(owner, limit)

    def active_job(self, owner: Optional[str] = None) -> Optional[str]:
        return self.repo.active_id(owner)

    def count_active(self) -> int:
        return self.repo.count_active()

    def read_file(self, job_id: str) -> Optional[bytes]:
        job = self.get(job_id)
        if not job or not job["has_file"]:
            return None
        return self.storage.get(job_id)

    def delete(self, job_id: str) -> str:
        """'deleted' | 'cancelled' | 'running' | 'missing'."""
        job = self.get(job_id)
        if not job:
            return "missing"
        if job["status"] == "running":
            return "running"  # CrewAI tidak bisa dihentikan di tengah jalan
        if job["status"] == "queued":
            if self.repo.cancel_queued(job_id):
                with self._lock:
                    self._discard_secret(job_id)
                return "cancelled"
            return "running"  # keburu diambil pekerja
        self.storage.delete(job_id)
        self.repo.delete(job_id)
        with self._lock:
            self._discard_secret(job_id)
        return "deleted"

    # --- key tersimpan (opsi 3b)
    def save_user_key(self, owner: str, provider: str, key: str) -> None:
        if not self.cipher:
            raise RuntimeError("Penyimpanan key tidak aktif di server ini")
        self.repo.save_key(owner, provider, self.cipher.encrypt(key))

    def has_user_key(self, owner: str, provider: str) -> bool:
        return self.repo.get_key(owner, provider) is not None

    def list_user_keys(self, owner: str) -> List[dict]:
        return self.repo.list_keys(owner)

    def delete_user_key(self, owner: str, provider: str) -> bool:
        return self.repo.delete_key(owner, provider)

    def shutdown(self) -> None:
        self._stop.set()  # menghentikan pekerja & heartbeat; job yang sedang berjalan menjadi basi -> interrupted
        self._wake.set()
        with self._lock:
            for jid in list(self._pending_runtime) + list(self.vault._keys):
                self._discard_secret(jid)
        self._worker.join(timeout=2)

    def _discard_secret(self, job_id: str) -> None:
        self.vault.discard(job_id)
        self._pending_runtime.pop(job_id, None)

    # ------------------------------------------------------------------ eksekusi
    def _loop(self) -> None:
        last_sweep = 0.0
        while not self._stop.is_set():
            try:
                now = datetime.now().timestamp()
                if now - last_sweep > max(5.0, self._stale_after / 3):
                    last_sweep = now
                    self.recover_stale()
                jid = self.repo.claim_next()
            except Exception:  # noqa: BLE001 - DB sempat putus (mis. Neon bangun): coba lagi
                log.exception("Pekerja gagal mengambil job")
                self._stop.wait(2)
                continue
            if jid is None:
                self._wake.wait(self._poll)
                self._wake.clear()
                continue
            try:
                self._run(jid)
            except Exception:  # noqa: BLE001
                log.exception("Job %s gagal tak terduga", jid)

    def _progress(self, job_id: str, step: str, status: str, detail: str = "") -> None:
        detail = self.vault.redact(detail)

        def apply(job: dict) -> None:
            if step in job["steps"]:
                st = job["steps"][step]
                if status == "info":
                    st["detail"] = detail
                else:
                    st["status"] = status
                    if detail:
                        st["detail"] = detail
                    if status == "error":
                        job["error_step"] = step
            label = {"running": "mulai", "done": "selesai", "skipped": "dilewati", "error": "GAGAL"}.get(status, "")
            line = " ".join(x for x in (step, label, detail) if x)
            job["log"].append({"t": _now(), "msg": line})
            del job["log"][:-MAX_LOG]

        self.repo.update(job_id, apply)

    def _sync_checkpoint(self, job_id: str, path: Path, seen: dict) -> None:
        """Salin checkpoint.json di folder kerja ke DB bila berubah (disk host tidak tahan restart)."""
        try:
            mt = path.stat().st_mtime_ns
        except OSError:
            return
        if seen.get("mtime") == mt:
            return
        meta = checkpoint.read_meta(path)
        if not meta:
            return
        self.repo.put_checkpoint(job_id, path.read_bytes(), meta)
        seen["mtime"] = mt

    def _resolve_runtime(self, job: dict) -> Optional[Runtime]:
        """Kredensial untuk job ini. Mock = tanpa key. Gagal -> UserFacingError."""
        job_id = job["id"]
        if job["mock"] or not job["byok"]:
            return None
        if job["key_source"] == "saved":
            enc = self.repo.get_key(job["owner"], job["provider"])
            if not enc or not self.cipher:
                raise UserFacingError("Key tersimpan tidak ditemukan. Masukkan API key lagi.")
            try:
                key = self.cipher.decrypt(enc)
            except CryptoError as e:
                raise UserFacingError(str(e)) from e
            self.vault.put(job_id, key)  # agar ikut disaring dari log/error
            m = job["models"] or {}
            return Runtime(job["provider"], key, m.get("planner", ""), m.get("writer", ""))
        with self._lock:
            runtime = self._pending_runtime.pop(job_id, None)
        if runtime is None:  # server restart saat job antre: key sesi hanya di memori dan sudah hilang
            raise UserFacingError("Server dimulai ulang sebelum job berjalan; API key tidak disimpan. Kirim ulang dengan key Anda.")
        return runtime

    def _heartbeat(self, job_id: str, stop: threading.Event) -> None:
        while not (stop.wait(self._heartbeat_every) or self._stop.is_set()):
            try:
                self.repo.heartbeat(job_id)
            except Exception:  # noqa: BLE001
                log.warning("Heartbeat job %s gagal", job_id)

    def _finish(self, job_id: str, fn: Callable[[dict], None]) -> None:
        """Ubah job hanya bila masih `running` (jangan menimpa job yang sudah dinyatakan mati/dihapus)."""
        def guarded(j: dict) -> None:
            if j["status"] == "running":
                fn(j)

        self.repo.update(job_id, guarded)

    def _run(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        workdir = Path(tempfile.mkdtemp(prefix=f"job-{job_id[:8]}-", dir=self.work_dir))
        out = workdir / "makalah.docx"
        ck_path = workdir / "checkpoint.json"
        seen: dict = {}
        stop_beat = threading.Event()
        threading.Thread(target=self._heartbeat, args=(job_id, stop_beat), daemon=True).start()

        def cb(step: str, status: str, detail: str = "") -> None:
            self._progress(job_id, step, status, detail)
            self._sync_checkpoint(job_id, ck_path, seen)

        sink = Sink()
        quiet = (contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink)) if self._quiet else ()
        try:
            runtime = self._resolve_runtime(job)
            ck = self.repo.get_checkpoint(job_id) if job.get("resume_from") else None
            if ck:
                ck_path.write_bytes(ck[0])
                seen["mtime"] = ck_path.stat().st_mtime_ns
            with contextlib.ExitStack() as stack:
                for cm in quiet:
                    stack.enter_context(cm)
                result = self._runner(job, cb, out, runtime) or {}
            if not out.is_file():
                raise RuntimeError("Proses selesai tetapi berkas .docx tidak terbentuk.")
            self.storage.put(job_id, out.read_bytes())

            def ok(j: dict) -> None:
                j["status"], j["finished_at"], j["has_file"] = "done", _now(), True
                j["usage"], j["stats"] = result.get("usage"), result.get("stats")
                j["resume"] = None

            self._finish(job_id, ok)
            self.repo.delete_checkpoint(job_id)  # selesai: draf tidak perlu disimpan
        except Exception as e:  # noqa: BLE001 - semua kegagalan harus tampil di UI
            # Traceback dibersihkan dari key sebelum menyentuh konsol/log host.
            if not self._quiet:
                print(self.vault.redact("".join(traceback.format_exception(e))), flush=True)
            safe = Exception(self.vault.redact(str(e)))
            friendly = str(safe) if isinstance(e, UserFacingError) else _friendly_error(safe)
            try:
                self._sync_checkpoint(job_id, ck_path, seen)
            except Exception:  # noqa: BLE001
                log.warning("Checkpoint terakhir job %s gagal disimpan", job_id)
            resume = self._resume_info(job_id)

            def fail(j: dict) -> None:
                j["status"], j["finished_at"] = "error", _now()
                j["error"] = friendly
                j["resume"] = resume

            self._finish(job_id, fail)
        finally:
            stop_beat.set()
            runtime = None  # lepas referensi ke key
            with self._lock:
                self._discard_secret(job_id)
            shutil.rmtree(workdir, ignore_errors=True)


def _friendly_error(e: Exception) -> str:
    """Pesan untuk pengguna. Detail mentah (sering JSON panjang dari penyedia) tidak ditampilkan."""
    msg = str(e).strip() or e.__class__.__name__
    low = msg.lower()
    if any(k in low for k in ("api key", "api_key", "authentication", "unauthorized", "invalid_argument",
                              "no auth credentials", "401")):
        return "API key ditolak penyedia (salah, kedaluwarsa, atau tanpa saldo). Periksa key Anda, lalu coba lagi."
    if any(k in low for k in ("insufficient", "credit", "payment required", "402")):
        return "Saldo/kredit di akun penyedia tidak cukup. Isi saldo atau pilih model yang lebih murah, lalu coba lagi."
    if any(k in low for k in ("rate limit", "ratelimit", "429", "quota", "resource_exhausted")):
        return "Batas kuota atau laju API tercapai. Tunggu sebentar atau ganti model, lalu coba lagi."
    if any(k in low for k in ("403", "forbidden", "permission denied")):
        return "Penyedia menolak akses (403). Periksa izin key Anda, atau jaringan server memblokir penyedia ini."
    if any(k in low for k in ("connection", "timeout", "timed out", "name resolution")):
        return "Tidak bisa terhubung ke penyedia model. Periksa koneksi internet, lalu coba lagi."
    if any(k in low for k in ("model not found", "does not exist", "no endpoints", "invalid model", "404")):
        return "Model tidak ditemukan di penyedia. Periksa penulisan id model, lalu coba lagi."
    first = (msg.splitlines()[0] if msg else e.__class__.__name__)
    return first.replace("litellm.", "")[:300]
