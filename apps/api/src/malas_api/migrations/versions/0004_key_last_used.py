"""user_api_keys.last_used_at: dasar penghapusan otomatis key tersimpan yang lama tak dipakai

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from malas_api.db import UtcDateTime

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_api_keys") as b:
        b.add_column(sa.Column("last_used_at", UtcDateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_api_keys") as b:
        b.drop_column("last_used_at")
