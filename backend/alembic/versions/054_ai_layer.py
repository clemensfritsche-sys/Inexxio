"""KI-Layer (ADR 004): ai_actions-Tabelle (Vorschlag → menschliche Bestätigung).

Der System-KI-User (role='ai') braucht keine Migration (Seeding beim Start);
KI-Läufe werden im bestehenden Event-Strom geloggt (keine eigene Tabelle).

Revision ID: 054
Revises: 053
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '054'
down_revision = '053'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "ai_actions" in insp.get_table_names():
        return
    op.create_table(
        "ai_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("proposed_by_ai_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_by_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_by_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_object_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_ai_actions_target_object_id", "ai_actions", ["target_object_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_actions CASCADE")
