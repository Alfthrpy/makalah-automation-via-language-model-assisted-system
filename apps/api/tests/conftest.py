"""Fixture bersama. Bila MALAS_TEST_DATABASE_URL diisi (Postgres), SELURUH suite berjalan di database itu;
tanpa itu, SQLite sementara per tes. Skema dikosongkan sebelum tiap tes."""
import os

import pytest
from sqlalchemy import create_engine, text

from malas_api import db as dbmod
from malas_api import jobs as jobsmod

PG_URL = os.getenv("MALAS_TEST_DATABASE_URL", "").strip()


def reset_postgres(url: str) -> None:
    eng = create_engine(dbmod.normalize_url(url))
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    eng.dispose()


@pytest.fixture(autouse=True)
def _database(monkeypatch):
    if PG_URL:
        reset_postgres(PG_URL)
        monkeypatch.setattr(jobsmod, "default_database_url", lambda root: PG_URL)
    yield


@pytest.fixture
def pg_url():
    if not PG_URL:
        pytest.skip("MALAS_TEST_DATABASE_URL tidak diisi (tes khusus Postgres)")
    return PG_URL
