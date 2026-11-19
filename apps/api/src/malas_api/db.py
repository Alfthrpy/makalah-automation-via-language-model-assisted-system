"""Lapisan database: model SQLAlchemy 2, pembuatan engine (Neon Postgres di produksi, SQLite untuk lokal/tes).

Skema dikelola Alembic (folder `migrations/`); `migrate()` dipanggil saat server naik.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text,
                        TypeDecorator, create_engine, event)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UtcDateTime(TypeDecorator):
    """Selalu timezone-aware UTC, juga di SQLite (yang membuang tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Pengguna. `external_id`: id dari penyedia auth (Clerk) atau, sementara, hash sesi anonim."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),
                      Index("ix_jobs_user_created", "user_id", "created_at"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))  # queued|running|done|error|interrupted|cancelled
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(UtcDateTime, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    mock: Mapped[bool] = mapped_column(Boolean, default=False)
    byok: Mapped[bool] = mapped_column(Boolean, default=False)
    key_source: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # session|saved
    provider: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resume_from: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    template: Mapped[str] = mapped_column(String(200), default="")
    template_path: Mapped[str] = mapped_column(String(500), default="")
    has_file: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_step: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    resume: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)  # {"available","done","total"}
    # request, models, steps, log, usage, stats, auto_resumed (besar: tidak dimuat saat daftar riwayat)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class JobCheckpoint(Base):
    """Draf makalah (outline + sub-bab jadi) agar job yang terputus bisa dilanjutkan. TANPA API key."""

    __tablename__ = "job_checkpoints"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)
    payload: Mapped[bytes] = mapped_column(LargeBinary)  # JSON terkompresi zlib
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class JobFile(Base):
    """Hasil .docx (implementasi `DbStorage`; bisa diganti R2 lewat antarmuka Storage)."""

    __tablename__ = "job_files"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class UserApiKey(Base):
    """API key BYOK yang SENGAJA disimpan pengguna; terenkripsi (Fernet). Tidak pernah dikembalikan lewat API."""

    __tablename__ = "user_api_keys"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


def normalize_url(url: str) -> str:
    """postgres:// dan postgresql:// (format Neon) -> driver psycopg 3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def make_engine(url: str) -> Engine:
    url = normalize_url(url)
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            dbapi_conn.isolation_level = None  # transaksi diatur manual (BEGIN IMMEDIATE) agar tidak "database is locked"
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        @event.listens_for(eng, "begin")
        def _begin(conn):  # noqa: ANN001
            conn.exec_driver_sql("BEGIN IMMEDIATE")

        return eng
    # Neon menidurkan compute saat idle: pre_ping + recycle pendek agar koneksi basi tidak dipakai.
    # prepare_threshold=None: aman di balik PgBouncer (pooler Neon, mode transaksi) yang tidak menjamin prepared statement.
    return create_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=240,
                         connect_args={"connect_timeout": 15, "prepare_threshold": None})


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{Path(path).resolve()}"


def migrate(engine: Engine) -> None:
    """Terapkan migrasi Alembic sampai head (aman dipanggil berulang)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":  # dua instance naik bersamaan: yang kedua menunggu, lalu no-op
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(727274)")
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


class Database:
    def __init__(self, url: str, *, run_migrations: bool = True, migrate_url: Optional[str] = None):
        """migrate_url: URL koneksi LANGSUNG (non-pooler) khusus migrasi, disarankan Neon. Kosong = pakai `url`."""
        self.url = normalize_url(url)
        self.engine = make_engine(self.url)
        if run_migrations:
            if migrate_url and normalize_url(migrate_url) != self.url:
                direct = make_engine(migrate_url)
                try:
                    migrate(direct)
                finally:
                    direct.dispose()
            else:
                migrate(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    @property
    def is_postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    def dispose(self) -> None:
        self.engine.dispose()


def database_url_from_env(env=os.environ) -> Optional[str]:
    url = (env.get("DATABASE_URL") or "").strip()
    return url or None


def migrate_url_from_env(env=os.environ) -> Optional[str]:
    url = (env.get("DATABASE_URL_DIRECT") or "").strip()
    return url or None
