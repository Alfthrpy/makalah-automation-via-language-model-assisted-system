"""Manajemen job pembuatan makalah untuk web UI.

- Satu pekerja (antrean FIFO): satu makalah diproses pada satu waktu agar kuota/rate-limit API
  dan file log bersama tidak berebut.
- Status disimpan di disk (output/jobs/<id>/job.json) supaya riwayat selamat dari restart.
- API key pengguna (BYOK) TIDAK PERNAH masuk job dict / disk: hanya di `Vault` (memori), diambil
  saat job mulai dan dibuang pada semua jalur akhir (selesai, gagal, batal, hapus).
- Setiap job punya pemilik (hash cookie sesi); job orang lain tidak terlihat.
- `runner` bisa disuntik, jadi API dapat diuji tanpa menjalankan CrewAI.
"""
import contextlib
import json
import os
import re
import shutil
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from malas import checkpoint
from malas.config import Runtime
from malas.steps import STEP_KEYS
from malas_api.vault import Sink, Vault, install_log_redaction

ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_LOG = 300
ACTIVE = {"queued", "running"}

# runner(job_dict, progress_cb, output_path, runtime_or_None) -> {"usage": {...}, "stats": {...}}
Runner = Callable[[dict, Callable[[str, str, str], None], Path, Optional[Runtime]], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
                 retention_hours: Optional[float] = None, quiet: bool = False):
        """retention_hours: job selesai yang lebih tua dihapus otomatis (None = simpan).
        quiet: buang semua stdout/stderr saat job berjalan (mode hosting: tanpa jejak di log host)."""
        self.root = Path(root)
        self.jobs_dir = self.root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner
        self._retention = retention_hours
        self._quiet = quiet
        self.vault = Vault()
        self._pending_runtime: Dict[str, Optional[Runtime]] = {}  # job_id -> kredensial, hanya di memori
        install_log_redaction(self.vault)
        self._lock = threading.RLock()
        self._jobs: Dict[str, dict] = {}
        self._futures: Dict[str, Future] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="malas-job")
        self._load_existing()
        self.purge()

    # ------------------------------------------------------------------ penyimpanan
    def _dir(self, job_id: str) -> Path:
        if not ID_RE.match(job_id):
            raise KeyError(job_id)
        return self.jobs_dir / job_id

    def _save(self, job: dict) -> None:
        d = self._dir(job["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, d / "job.json")

    def _load_existing(self) -> None:
        for f in self.jobs_dir.glob("*/job.json"):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
                if not ID_RE.match(job.get("id", "")):
                    continue
            except (OSError, ValueError):
                continue
            if job.get("status") in ACTIVE:  # server mati saat job berjalan
                job["status"], job["error"] = "interrupted", "Server berhenti saat job ini berjalan."
                job["finished_at"] = job.get("finished_at") or _now()
                job["resume"] = self._resume_info(job["id"])
                self._save(job)
            self._jobs[job["id"]] = job

    def _resume_info(self, job_id: str) -> Optional[dict]:
        """Info 'bisa dilanjutkan' dari checkpoint di disk (None bila tidak ada)."""
        meta = checkpoint.read_meta(self._dir(job_id) / "checkpoint.json")
        if not meta:
            return None
        return {"available": bool(meta["outline"]), "done": meta["done"], "total": meta["total"]}

    def purge(self) -> int:
        """Hapus job selesai yang melewati masa simpan. Dipanggil lazy (tanpa thread latar)."""
        if not self._retention:
            return 0
        limit = datetime.now(timezone.utc) - timedelta(hours=self._retention)
        with self._lock:
            old = [
                j["id"] for j in self._jobs.values()
                if j["status"] not in ACTIVE and j.get("finished_at")
                and datetime.fromisoformat(j["finished_at"]) < limit
            ]
            for jid in old:
                self._jobs.pop(jid, None)
                self._futures.pop(jid, None)
        for jid in old:
            shutil.rmtree(self._dir(jid), ignore_errors=True)
        return len(old)

    # ------------------------------------------------------------------ API
    def submit(self, request: dict, mock: bool, template_path: str, template_name: str, *,
               owner: str = "", runtime: Optional[Runtime] = None, resume_from: Optional[str] = None) -> dict:
        self.purge()
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
            "byok": runtime is not None,  # hanya penanda; key TIDAK disimpan di sini
            "provider": runtime.provider_id if runtime else None,
            "models": {"planner": runtime.planner_model, "writer": runtime.writer_model} if runtime else None,
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
        with self._lock:
            if resume_from:  # salin checkpoint job asal; job asal tetap utuh (bisa dilanjutkan lagi)
                src = self._dir(resume_from) / "checkpoint.json"
                if not src.is_file():
                    raise ValueError("Checkpoint job asal tidak ditemukan")
                self._dir(job_id).mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, self._dir(job_id) / "checkpoint.json")
            if runtime is not None:
                self.vault.put(job_id, runtime.api_key)
            self._jobs[job_id] = job
            self._save(job)
            # runtime (berisi key) dipegang HANYA oleh dict ini; dibuang saat job mulai
            self._pending_runtime[job_id] = runtime if runtime is not None else None
            self._futures[job_id] = self._pool.submit(self._run, job_id)
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id) if ID_RE.match(job_id) else None
            return json.loads(json.dumps(job)) if job else None  # salinan aman untuk dibaca thread lain

    def list(self, visible: Callable[[dict], bool] = lambda j: True, limit: int = 30) -> List[dict]:
        self.purge()
        with self._lock:
            jobs = sorted((j for j in self._jobs.values() if visible(j)), key=lambda j: j["created_at"], reverse=True)[:limit]
            return [
                {k: j.get(k) for k in ("id", "status", "title", "created_at", "finished_at", "mock", "byok", "has_file", "resume")}
                for j in jobs
            ]

    def active_job(self, visible: Callable[[dict], bool] = lambda j: True) -> Optional[str]:
        with self._lock:
            for j in self._jobs.values():
                if j["status"] in ACTIVE and visible(j):
                    return j["id"]
        return None

    def file_path(self, job_id: str) -> Optional[Path]:
        job = self.get(job_id)
        if not job or not job["has_file"]:
            return None
        p = self._dir(job_id) / "makalah.docx"
        return p if p.is_file() else None

    def delete(self, job_id: str) -> str:
        """'deleted' | 'cancelled' | 'running' | 'missing'."""
        with self._lock:
            job = self._jobs.get(job_id) if ID_RE.match(job_id) else None
            if not job:
                return "missing"
            if job["status"] == "running":
                return "running"  # CrewAI tidak bisa dihentikan di tengah jalan
            fut = self._futures.get(job_id)
            if job["status"] == "queued" and fut and fut.cancel():
                job["status"], job["finished_at"] = "cancelled", _now()
                self._discard_secret(job_id)
                self._save(job)
                return "cancelled"
            self._jobs.pop(job_id, None)
            self._futures.pop(job_id, None)
            self._discard_secret(job_id)
        shutil.rmtree(self._dir(job_id), ignore_errors=True)
        return "deleted"

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            for jid in list(self._pending_runtime):
                self._discard_secret(jid)

    def _discard_secret(self, job_id: str) -> None:
        self.vault.discard(job_id)
        self._pending_runtime.pop(job_id, None)

    # ------------------------------------------------------------------ eksekusi
    def _update(self, job_id: str, fn: Callable[[dict], None]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # dihapus saat berjalan
                return
            fn(job)
            self._save(job)

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

        self._update(job_id, apply)

    def _run(self, job_id: str) -> None:
        def start(job: dict) -> None:
            job["status"], job["started_at"] = "running", _now()

        self._update(job_id, start)
        # Ambil runtime (key) dari memori; setelah ini referensi di brankas/antrean dibuang.
        with self._lock:
            runtime = self._pending_runtime.pop(job_id, None)
        job = self.get(job_id)
        if job is None:
            self.vault.discard(job_id)
            return
        out = self._dir(job_id) / "makalah.docx"

        def cb(step: str, status: str, detail: str = "") -> None:
            self._progress(job_id, step, status, detail)

        sink = Sink()
        quiet = (contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink)) if self._quiet else ()
        try:
            with contextlib.ExitStack() as stack:
                for cm in quiet:
                    stack.enter_context(cm)
                result = self._runner(job, cb, out, runtime) or {}
            if not out.is_file():
                raise RuntimeError("Proses selesai tetapi berkas .docx tidak terbentuk.")

            def ok(j: dict) -> None:
                j["status"], j["finished_at"], j["has_file"] = "done", _now(), True
                j["usage"], j["stats"] = result.get("usage"), result.get("stats")
                j["resume"] = None

            self._update(job_id, ok)
            (self._dir(job_id) / "checkpoint.json").unlink(missing_ok=True)  # selesai: draf tidak perlu disimpan
        except Exception as e:  # noqa: BLE001 - semua kegagalan harus tampil di UI
            # Traceback dibersihkan dari key sebelum menyentuh konsol/log host.
            if not self._quiet:
                print(self.vault.redact("".join(traceback.format_exception(e))), flush=True)
            friendly = _friendly_error(Exception(self.vault.redact(str(e))))

            resume = self._resume_info(job_id)

            def fail(j: dict) -> None:
                j["status"], j["finished_at"] = "error", _now()
                j["error"] = friendly
                j["resume"] = resume

            self._update(job_id, fail)
        finally:
            runtime = None  # lepas referensi ke key
            self.vault.discard(job_id)


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
