"""Penyimpanan berkas hasil (.docx). Antarmuka kecil agar backend bisa diganti (DB sekarang, R2 nanti)."""
from typing import Protocol

from sqlalchemy.orm import sessionmaker

from malas_api.db import JobFile


class Storage(Protocol):
    def put(self, job_id: str, content: bytes) -> None: ...
    def get(self, job_id: str) -> bytes | None: ...
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

    def get(self, job_id: str) -> bytes | None:
        with self._session() as s:
            row = s.get(JobFile, job_id)
            return bytes(row.content) if row else None

    def delete(self, job_id: str) -> None:
        with self._session.begin() as s:
            row = s.get(JobFile, job_id)
            if row:
                s.delete(row)


class S3Storage:
    """Objek di bucket kompatibel S3 (Cloudflare R2). Kunci: `jobs/<job_id>.docx`; bucket sebaiknya privat
    (unduhan selalu lewat API yang memeriksa pemilik, tidak ada URL publik)."""

    def __init__(self, client, bucket: str, prefix: str = "jobs/"):
        self._c, self._bucket, self._prefix = client, bucket, prefix

    def _key(self, job_id: str) -> str:
        return f"{self._prefix}{job_id}.docx"

    def put(self, job_id: str, content: bytes) -> None:
        self._c.put_object(Bucket=self._bucket, Key=self._key(job_id), Body=content,
                           ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def get(self, job_id: str) -> bytes | None:
        try:
            return self._c.get_object(Bucket=self._bucket, Key=self._key(job_id))["Body"].read()
        except self._c.exceptions.NoSuchKey:
            return None

    def delete(self, job_id: str) -> None:
        self._c.delete_object(Bucket=self._bucket, Key=self._key(job_id))  # idempoten: kunci tak ada = tidak error


R2_VARS = ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


def storage_from_env(env=None) -> S3Storage | None:
    """R2 bila keempat env terisi; kosong semua -> None (pakai DbStorage). Terisi sebagian -> error jelas."""
    import os

    env = os.environ if env is None else env
    vals = {k: (env.get(k) or "").strip() for k in R2_VARS}
    if not any(vals.values()):
        return None
    missing = [k for k, v in vals.items() if not v]
    if missing:
        raise RuntimeError("Konfigurasi R2 tidak lengkap, belum diisi: " + ", ".join(missing))
    import boto3  # impor lambat: tidak membebani memori bila R2 tidak dipakai
    from botocore.config import Config

    client = boto3.client(
        "s3", endpoint_url=vals["R2_ENDPOINT_URL"], aws_access_key_id=vals["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=vals["R2_SECRET_ACCESS_KEY"], region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"},
                      connect_timeout=5, read_timeout=30),
    )
    return S3Storage(client, vals["R2_BUCKET"])
