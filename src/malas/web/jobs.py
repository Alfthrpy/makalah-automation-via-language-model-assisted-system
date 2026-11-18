"""Manajemen job pembuatan makalah untuk web UI.

- Satu pekerja (antrean FIFO): satu makalah diproses pada satu waktu agar kuota/rate-limit API
  dan file log bersama tidak berebut.
- Status disimpan di disk (output/jobs/<id>/job.json) supaya riwayat selamat dari restart.
- `runner` bisa disuntik, jadi API dapat diuji tanpa menjalankan CrewAI.
"""
import json
import os
import re
import shutil
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from malas.steps import STEP_KEYS

ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_LOG = 300
ACTIVE = {"queued", "running"}

# runner(job_dict, progress_cb, output_path) -> {"usage": {...}, "stats": {...}}
Runner = Callable[[dict, Callable[[str, str, str], None], Path], dict]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_runner(job: dict, progress: Callable[[str, str, str], None], output_path: Path) -> dict:
    """Jalankan MalasFlow sungguhan (impor ditunda: CrewAI berat dan tidak perlu saat server naik)."""
    from malas import config
    from malas.main import MalasFlow

    req = job["request"]
    config.set_mock_override(True if job["mock"] else None)
    try:
        flow = MalasFlow()
        flow.input_data = dict(req)
        flow.template_path = job["template_path"]
        flow.output_path = str(output_path)
        flow.progress = progress
        flow.kickoff()
        return {"usage": getattr(flow, "usage", {}), "stats": getattr(flow, "stats", {})}
    finally:
        config.set_mock_override(None)


class JobManager:
    def __init__(self, root: Path, runner: Runner = default_runner):
        self.root = Path(root)
        self.jobs_dir = self.root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner
        self._lock = threading.RLock()
        self._jobs: Dict[str, dict] = {}
        self._futures: Dict[str, Future] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="malas-job")
        self._load_existing()

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
                self._save(job)
            self._jobs[job["id"]] = job

    # ------------------------------------------------------------------ API
    def submit(self, request: dict, mock: bool, template_path: str, template_name: str) -> dict:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "title": request["judul"],
            "mock": mock,
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
            self._jobs[job_id] = job
            self._save(job)
            self._futures[job_id] = self._pool.submit(self._run, job_id)
        return self.get(job_id)

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id) if ID_RE.match(job_id) else None
            return json.loads(json.dumps(job)) if job else None  # salinan aman untuk dibaca thread lain

    def list(self, limit: int = 30) -> List[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
            return [
                {k: j[k] for k in ("id", "status", "title", "created_at", "finished_at", "mock", "has_file")}
                for j in jobs
            ]

    def active_job(self) -> Optional[str]:
        with self._lock:
            for j in self._jobs.values():
                if j["status"] in ACTIVE:
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
                self._save(job)
                return "cancelled"
            self._jobs.pop(job_id, None)
            self._futures.pop(job_id, None)
        shutil.rmtree(self._dir(job_id), ignore_errors=True)
        return "deleted"

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ eksekusi
    def _update(self, job_id: str, fn: Callable[[dict], None]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # dihapus saat berjalan
                return
            fn(job)
            self._save(job)

    def _progress(self, job_id: str, step: str, status: str, detail: str = "") -> None:
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
        job = self.get(job_id)
        if job is None:
            return
        out = self._dir(job_id) / "makalah.docx"

        def cb(step: str, status: str, detail: str = "") -> None:
            self._progress(job_id, step, status, detail)

        try:
            result = self._runner(job, cb, out) or {}
            if not out.is_file():
                raise RuntimeError("Proses selesai tetapi berkas .docx tidak terbentuk.")

            def ok(j: dict) -> None:
                j["status"], j["finished_at"], j["has_file"] = "done", _now(), True
                j["usage"], j["stats"] = result.get("usage"), result.get("stats")

            self._update(job_id, ok)
        except Exception as e:  # noqa: BLE001 - semua kegagalan harus tampil di UI
            traceback.print_exc()

            def fail(j: dict) -> None:
                j["status"], j["finished_at"] = "error", _now()
                j["error"] = _friendly_error(e)

            self._update(job_id, fail)


def _friendly_error(e: Exception) -> str:
    """Pesan untuk pengguna. Detail mentah (sering JSON panjang dari penyedia) hanya di konsol server."""
    msg = str(e).strip() or e.__class__.__name__
    low = msg.lower()
    if any(k in low for k in ("api key", "api_key", "authentication", "unauthorized", "invalid_argument")):
        return "API key tidak valid atau belum diisi. Periksa file .env, lalu coba lagi."
    if any(k in low for k in ("rate limit", "ratelimit", "429", "quota", "resource_exhausted")):
        return "Batas kuota atau laju API tercapai. Tunggu sebentar atau ganti model, lalu coba lagi."
    if any(k in low for k in ("connection", "timeout", "timed out", "name resolution")):
        return "Tidak bisa terhubung ke penyedia model. Periksa koneksi internet, lalu coba lagi."
    return (msg.splitlines()[0] if msg else e.__class__.__name__)[:300]
