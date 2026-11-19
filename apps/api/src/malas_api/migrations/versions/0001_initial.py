"""skema awal: users, jobs, job_checkpoints, job_files, user_api_keys

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from malas_api.db import UtcDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("external_id", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("started_at", UtcDateTime(), nullable=True),
        sa.Column("finished_at", UtcDateTime(), nullable=True),
        sa.Column("heartbeat_at", UtcDateTime(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("byok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("key_source", sa.String(10), nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("resume_from", sa.String(32), nullable=True),
        sa.Column("template", sa.String(200), nullable=False, server_default=""),
        sa.Column("template_path", sa.String(500), nullable=False, server_default=""),
        sa.Column("has_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_step", sa.String(30), nullable=True),
        sa.Column("resume", JSONType, nullable=True),
        sa.Column("data", JSONType, nullable=False),
    )
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])
    op.create_index("ix_jobs_user_created", "jobs", ["user_id", "created_at"])
    op.create_table(
        "job_checkpoints",
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("meta", JSONType, nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "job_files",
        sa.Column("job_id", sa.String(32), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_table(
        "user_api_keys",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.String(30), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
    )


def downgrade() -> None:
    for t in ("user_api_keys", "job_files", "job_checkpoints", "jobs", "users"):
        op.drop_table(t)
