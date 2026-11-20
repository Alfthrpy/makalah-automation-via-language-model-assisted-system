"""Akses data job/checkpoint/key. Satu-satunya tempat yang bicara SQL.

Bentuk job di luar lapisan ini tetap dict seperti sebelumnya (id, owner, status, steps, log, ...), jadi
`app.py` dan klien tidak berubah. Kolom yang sering di-query (status, waktu, pemilik) berupa kolom nyata;
bagian besar (request, steps, log, usage, stats) ada di kolom JSON `data`.
"""
from __future__ import annotations

import copy
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from malas_api.db import Database, Job, JobCheckpoint, Usage, User, UserApiKey, utcnow

ACTIVE = ("queued", "running")
DATA_KEYS = ("request", "models", "steps", "log", "usage", "stats", "auto_resumed", "quota_day")
COLUMN_KEYS = ("status", "started_at", "finished_at", "title", "mock", "byok", "key_source", "provider",
               "resume_from", "template", "template_path", "has_file", "error", "error_step", "resume")
TIME_KEYS = ("created_at", "started_at", "finished_at")
SUMMARY_KEYS = ("id", "status", "title", "created_at", "finished_at", "mock", "byok", "has_file", "resume")
STEP_ORDER = ("input", "outline", "fulltext", "tulis", "sitasi", "pengantar", "docx")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


def to_dict(row: Job, owner: str) -> dict:
    d = copy.deepcopy(row.data or {})  # salinan penuh: mutasi di tempat harus terdeteksi sebagai perubahan
    d.update(id=row.id, owner=owner, created_at=_iso(row.created_at))
    for k in COLUMN_KEYS:
        v = getattr(row, k)
        d[k] = _iso(v) if k in TIME_KEYS else copy.deepcopy(v)
    for k in DATA_KEYS:
        d.setdefault(k, None)
    return d


def _apply(row: Job, d: dict) -> None:
    for k in COLUMN_KEYS:
        v = d.get(k)
        setattr(row, k, _dt(v) if k in TIME_KEYS else v)
    row.data = {k: d.get(k) for k in DATA_KEYS}  # objek baru: perubahan terdeteksi


class Repo:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------ pengguna
    def ensure_user(self, external_id: str) -> str:
        for _ in range(2):
            with self.db.session.begin() as s:
                uid = s.scalar(select(User.id).where(User.external_id == external_id))
                if uid:
                    return uid
                uid = uuid.uuid4().hex
                try:
                    with s.begin_nested():
                        s.add(User(id=uid, external_id=external_id))
                    return uid
                except IntegrityError:  # balapan: pengguna dibuat proses lain; baca ulang
                    continue
        raise RuntimeError("Gagal membuat pengguna")

    def user_id(self, external_id: str) -> Optional[str]:
        with self.db.session() as s:
            return s.scalar(select(User.id).where(User.external_id == external_id))

    # ------------------------------------------------------------------ job
    def create_job(self, d: dict) -> None:
        uid = self.ensure_user(d["owner"])
        row = Job(id=d["id"], user_id=uid, created_at=_dt(d["created_at"]) or utcnow())
        _apply(row, d)
        with self.db.session.begin() as s:
            s.add(row)

    def get(self, job_id: str) -> Optional[dict]:
        with self.db.session() as s:
            r = s.execute(select(Job, User.external_id).join(User, User.id == Job.user_id).where(Job.id == job_id)).first()
            return to_dict(r[0], r[1]) if r else None

    def update(self, job_id: str, fn: Callable[[dict], None]) -> Optional[dict]:
        """Baca-ubah-tulis atomik (baris dikunci). `fn` memutasi dict; None bila job sudah dihapus."""
        with self.db.session.begin() as s:
            r = s.execute(select(Job, User.external_id).join(User, User.id == Job.user_id)
                          .where(Job.id == job_id).with_for_update(of=Job)).first()
            if not r:
                return None
            d = to_dict(r[0], r[1])
            fn(d)
            _apply(r[0], d)
            return d

    def queue_ranks(self) -> dict:
        """id job antre -> posisi (1 = berikutnya dijalankan)."""
        with self.db.session() as s:
            ids = list(s.scalars(select(Job.id).where(Job.status == "queued").order_by(Job.created_at, Job.id)))
        return {jid: i + 1 for i, jid in enumerate(ids)}

    def queue_position(self, job_id: str) -> Optional[int]:
        return self.queue_ranks().get(job_id)

    @staticmethod
    def _progress(steps: Optional[dict]) -> Tuple[Optional[dict], Optional[str], str]:
        """(progres tahap {done,total}, kunci tahap berjalan, detail tahap berjalan) dari data steps."""
        if not steps:
            return None, None, ""
        done = sum(1 for k in STEP_ORDER if (steps.get(k) or {}).get("status") in ("done", "skipped"))
        cur = next((k for k in STEP_ORDER if (steps.get(k) or {}).get("status") == "running"), None)
        return {"done": done, "total": len(STEP_ORDER)}, cur, ((steps.get(cur) or {}).get("detail") or "") if cur else ""

    def list(self, owner: Optional[str] = None, limit: int = 30) -> List[dict]:
        q = (select(Job.id, Job.status, Job.title, Job.created_at, Job.finished_at, Job.mock, Job.byok,
                    Job.has_file, Job.resume, Job.data)
             .join(User, User.id == Job.user_id).order_by(Job.created_at.desc(), Job.id).limit(limit))
        if owner is not None:
            q = q.where(User.external_id == owner)
        with self.db.session() as s:
            rows = list(s.execute(q))
        ranks = self.queue_ranks() if any(r._mapping["status"] == "queued" for r in rows) else {}
        out = []
        for r in rows:
            m = r._mapping
            item = {k: (_iso(m[k]) if k in TIME_KEYS else m[k]) for k in SUMMARY_KEYS}
            data = m["data"] or {}
            progress, cur, detail = self._progress(data.get("steps"))
            item["mata_kuliah"] = (data.get("request") or {}).get("mata_kuliah")
            item["progress"] = progress if m["status"] in ("queued", "running") else None
            item["current_step"] = cur
            item["current_detail"] = detail
            item["queue_position"] = ranks.get(m["id"])
            out.append(item)
        return out

    def active_id(self, owner: Optional[str] = None) -> Optional[str]:
        q = select(Job.id).join(User, User.id == Job.user_id).where(Job.status.in_(ACTIVE)).order_by(Job.created_at).limit(1)
        if owner is not None:
            q = q.where(User.external_id == owner)
        with self.db.session() as s:
            return s.scalar(q)

    def count_active(self) -> int:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))) or 0

    def claim_next(self) -> Optional[str]:
        """Ambil job antre tertua dan tandai running. FOR UPDATE SKIP LOCKED di Postgres (aman untuk banyak
        pekerja); UPDATE bersyarat (status='queued') menjamin satu pemenang di semua database."""
        now = utcnow()
        with self.db.session.begin() as s:
            jid = s.scalar(select(Job.id).where(Job.status == "queued").order_by(Job.created_at, Job.id)
                           .limit(1).with_for_update(skip_locked=True))
            if not jid:
                return None
            n = s.execute(update(Job).where(Job.id == jid, Job.status == "queued")
                          .values(status="running", started_at=now, heartbeat_at=now)).rowcount
            return jid if n == 1 else None

    def heartbeat(self, job_id: str) -> None:
        with self.db.session.begin() as s:
            s.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(heartbeat_at=utcnow()))

    def stale_running(self, older_than: float) -> List[str]:
        limit = utcnow() - timedelta(seconds=older_than)
        with self.db.session() as s:
            return list(s.scalars(select(Job.id).where(Job.status == "running",
                                                       (Job.heartbeat_at.is_(None)) | (Job.heartbeat_at <= limit))))

    def cancel_queued(self, job_id: str) -> bool:
        with self.db.session.begin() as s:
            return s.execute(update(Job).where(Job.id == job_id, Job.status == "queued")
                             .values(status="cancelled", finished_at=utcnow())).rowcount == 1

    def delete(self, job_id: str) -> None:
        with self.db.session.begin() as s:
            s.execute(delete(Job).where(Job.id == job_id))  # checkpoint & berkas ikut (ON DELETE CASCADE)

    def expired(self, before: datetime) -> List[str]:
        with self.db.session() as s:
            return list(s.scalars(select(Job.id).where(Job.status.notin_(ACTIVE), Job.finished_at.isnot(None),
                                                       Job.finished_at < before)))

    # ------------------------------------------------------------------ checkpoint
    def put_checkpoint(self, job_id: str, raw_json: bytes, meta: dict) -> None:
        blob = zlib.compress(raw_json, 6)
        with self.db.session.begin() as s:
            row = s.get(JobCheckpoint, job_id)
            if row:
                row.payload, row.meta, row.updated_at = blob, meta, utcnow()
            else:
                s.add(JobCheckpoint(job_id=job_id, payload=blob, meta=meta))

    def get_checkpoint(self, job_id: str) -> Optional[Tuple[bytes, dict]]:
        with self.db.session() as s:
            row = s.get(JobCheckpoint, job_id)
            return (zlib.decompress(bytes(row.payload)), dict(row.meta)) if row else None

    def checkpoint_meta(self, job_id: str) -> Optional[dict]:
        with self.db.session() as s:
            return s.scalar(select(JobCheckpoint.meta).where(JobCheckpoint.job_id == job_id))

    def delete_checkpoint(self, job_id: str) -> None:
        with self.db.session.begin() as s:
            s.execute(delete(JobCheckpoint).where(JobCheckpoint.job_id == job_id))

    def copy_checkpoint(self, src: str, dst: str) -> bool:
        with self.db.session.begin() as s:
            row = s.get(JobCheckpoint, src)
            if not row:
                return False
            s.add(JobCheckpoint(job_id=dst, payload=bytes(row.payload), meta=dict(row.meta)))
            return True

    # ------------------------------------------------------------------ API key tersimpan (terenkripsi)
    def save_key(self, owner: str, provider: str, ciphertext: str) -> None:
        uid = self.ensure_user(owner)
        with self.db.session.begin() as s:
            row = s.get(UserApiKey, (uid, provider))
            if row:
                row.ciphertext, row.updated_at = ciphertext, utcnow()
            else:
                s.add(UserApiKey(user_id=uid, provider=provider, ciphertext=ciphertext))

    def get_key(self, owner: str, provider: str) -> Optional[str]:
        with self.db.session() as s:
            return s.scalar(select(UserApiKey.ciphertext).join(User, User.id == UserApiKey.user_id)
                            .where(User.external_id == owner, UserApiKey.provider == provider))

    def list_keys(self, owner: str) -> List[dict]:
        with self.db.session() as s:
            rows = s.execute(select(UserApiKey.provider, UserApiKey.updated_at).join(User, User.id == UserApiKey.user_id)
                             .where(User.external_id == owner).order_by(UserApiKey.provider))
            return [{"provider": r.provider, "saved_at": _iso(r.updated_at)} for r in rows]

    def delete_key(self, owner: str, provider: str) -> bool:
        uid = self.user_id(owner)
        if not uid:
            return False
        with self.db.session.begin() as s:
            return s.execute(delete(UserApiKey).where(UserApiKey.user_id == uid, UserApiKey.provider == provider)).rowcount > 0

    # ------------------------------------------------------------------ kuota harian
    def quota_used(self, owner: str, day: str) -> int:
        with self.db.session() as s:
            return s.scalar(select(Usage.jobs).join(User, User.id == Usage.user_id)
                            .where(User.external_id == owner, Usage.day == day)) or 0

    def consume_quota(self, owner: str, day: str, limit: int) -> bool:
        """Tambah 1 pemakaian hari ini bila belum mencapai `limit`. Atomik: UPDATE bersyarat, tanpa baca-lalu-tulis."""
        uid = self.ensure_user(owner)
        for _ in range(3):
            with self.db.session.begin() as s:
                if s.execute(update(Usage).where(Usage.user_id == uid, Usage.day == day, Usage.jobs < limit)
                             .values(jobs=Usage.jobs + 1)).rowcount == 1:
                    return True
                if s.get(Usage, (uid, day)) is not None:
                    return False  # baris ada tapi sudah di batas
                try:
                    with s.begin_nested():
                        s.add(Usage(user_id=uid, day=day, jobs=1))
                    return True
                except IntegrityError:  # balapan pembuatan baris: ulangi UPDATE
                    continue
        return False

    def refund_quota(self, owner: str, day: str) -> None:
        uid = self.user_id(owner)
        if not uid:
            return
        with self.db.session.begin() as s:
            s.execute(update(Usage).where(Usage.user_id == uid, Usage.day == day, Usage.jobs > 0)
                      .values(jobs=Usage.jobs - 1))
