"""tabel user_logos: logo kampus/sekolah per pengguna (PNG ternormalisasi, untuk sampul makalah)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op
from malas_api.db import UtcDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_logos",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_logos")
