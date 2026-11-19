"""Penyimpanan berkas hasil (.docx). Antarmuka kecil agar backend bisa diganti (DB sekarang, R2 nanti)."""
from typing import Optional, Protocol

from sqlalchemy.orm import sessionmaker

from malas_api.db import JobFile


class Storage(Protocol):
    def put(self, job_id: str, content: bytes) -> None: ...
    def get(self, job_id: str) -> Optional[bytes]: ...
    def delete(self, job_id: str) -> None: ...


class DbStorage:
    """Simpan sebagai bytea di Postgres. Cukup untuk MVP (.docx ± puluhan-ratusan KB; dibersihkan oleh retensi)."""

    def __init__(self, session: sessionmaker):
        self._session = session

    def put(self, job_id: str, content: bytes) -> None:
        with self._session.begin() as s:
            row = s.get(JobFile, job_id)
            if row:
                row.content, row.size = content, len(content)
            else:
                s.add(JobFile(job_id=job_id, content=content, size=len(content)))

    def get(self, job_id: str) -> Optional[bytes]:
        with self._session() as s:
            row = s.get(JobFile, job_id)
            return bytes(row.content) if row else None

    def delete(self, job_id: str) -> None:
        with self._session.begin() as s:
            row = s.get(JobFile, job_id)
            if row:
                s.delete(row)
