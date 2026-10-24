"""attachments-Tabelle (Foto-/Bild-Uploads, per Token ausgeliefert).

Revision ID: 053
Revises: 052
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '053'
down_revision = '052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "attachments" in insp.get_table_names():
        return
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False, server_default="image/jpeg"),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_attachments_token", "attachments", ["token"], unique=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS attachments CASCADE")
