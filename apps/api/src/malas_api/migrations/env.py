"""Lingkungan Alembic. Dipakai lewat `malas_api.db.migrate()` (koneksi disuntik) atau CLI:
    DATABASE_URL=... uv run --package malas-api alembic -c apps/api/alembic.ini upgrade head
"""
from alembic import context
from sqlalchemy import engine_from_config, pool

from malas_api.db import Base, normalize_url

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    import os

    url = normalize_url(os.environ["DATABASE_URL"])
    engine = engine_from_config({"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
