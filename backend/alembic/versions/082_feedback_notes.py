"""082 – Testnotizen der Oberfläche (in-app Feedback).

Eine Notiz ist ein **Meta-Artefakt über dem System**, kein Geschäftsobjekt: keine
Objektnummer, kein Eintrag im Event-Strom, kein Feed-Typ (gleiche Einordnung wie
``ai_actions``, ``attachments``, ``audit_log``). Sie hält den Kommentar plus den
automatisch mitgeschnittenen Kontext – Route, geöffneter Datensatz, Anker am geklickten
Element (``anchor``) und Umgebung inkl. der letzten Laufzeitfehler (``context``).

Index-Wahl folgt den drei tatsächlichen Abfragen: Pins der aktuellen Seite (``route``),
«meine Notizen» (``created_by``) und die offene Liste (``status``).

Revision ID: 082
Revises: 081
Create Date: 2026-07-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '082'
down_revision = '081'
branch_labels = None
depends_on = None

TABLE = "feedback_notes"


def upgrade() -> None:
    if TABLE in set(inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("route", sa.String(length=500), server_default="", nullable=False),
        sa.Column("target_object_id", sa.BigInteger(), nullable=True),
        sa.Column("anchor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{TABLE}_route", TABLE, ["route"])
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
    op.create_index(f"ix_{TABLE}_created_by", TABLE, ["created_by"])
    op.create_index(f"ix_{TABLE}_target_object_id", TABLE, ["target_object_id"])


def downgrade() -> None:
    if TABLE in set(inspect(op.get_bind()).get_table_names()):
        op.drop_table(TABLE)
