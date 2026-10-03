"""Refund-Schritt statt return-Schritt: return_receipts entfällt.

Die Retoure/Erstattung wird neu als **ganz normaler Auftrag** modelliert (Artikel + verkaufte
Instanzen als Subjekt, ``reason='return'`` + ``parent_order_id``). Die Auflösung komponiert
bestehende Module:
  • physischer Rückfluss (sold → in_stock) über die **Bewegung** + den Abschluss
    (``process._finalize_subjects``) – KEIN eigener Rücknahme-Schritt mehr,
  • Geld zurück über den neuen Schritt **``refund``** = ``sales`` im Kredit-Modus (die
    ``sales``-Spalten kind/original_sale_id/credit_note_number/stripe_refund_id/refunded_at
    aus Migration 048 bleiben erhalten und werden weiterverwendet).

Damit ist die Fachtabelle ``return_receipts`` (Abschluss-Marker des alten ``return``-Schritts)
überflüssig und wird entfernt.

Revision ID: 049
Revises: 048
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '049'
down_revision = '048'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "return_receipts" in insp.get_table_names():
        op.drop_table("return_receipts")


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "return_receipts" not in insp.get_table_names():
        op.create_table(
            "return_receipts",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("step_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("received_by_id", sa.BigInteger(), nullable=True),
            sa.Column("location_type", sa.String(length=20), nullable=True),
            sa.Column("location_id", sa.BigInteger(), nullable=True),
            sa.Column("to_inspection", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
