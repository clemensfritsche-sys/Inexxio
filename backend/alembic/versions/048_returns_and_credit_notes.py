"""Retouren + Gutschriften: return_receipts-Tabelle + Sale-Gutschrift-Felder.

Eine Retoure ist ein Unter-Auftrag (``orders.reason='return'``, freie Spalte – keine
Schemaänderung nötig). Sie komponiert bestehende Module plus:
  • Schritt «Rücknahme» (``return``) → Fachtabelle ``return_receipts`` (Spiegel von
    ``disposals``): nimmt verkaufte Instanzen zurück (Menge/Disposition wiederhergestellt).
  • «Gutschrift» = ``sales`` im Kredit-Modus → neue Spalten ``kind``/``original_sale_id``/
    ``credit_note_number``/``stripe_refund_id``/``refunded_at``.

Revision ID: 048
Revises: 047
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '048'
down_revision = '047'
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    sale_cols = {c["name"] for c in insp.get_columns("sales")} if "sales" in insp.get_table_names() else set()
    if "kind" not in sale_cols:
        op.add_column("sales", sa.Column("kind", sa.String(length=8), nullable=False, server_default="sale"))
    if "original_sale_id" not in sale_cols:
        op.add_column("sales", sa.Column("original_sale_id", sa.BigInteger(), nullable=True, index=True))
    if "credit_note_number" not in sale_cols:
        op.add_column("sales", sa.Column("credit_note_number", sa.String(length=60), nullable=True))
    if "stripe_refund_id" not in sale_cols:
        op.add_column("sales", sa.Column("stripe_refund_id", sa.String(length=80), nullable=True, index=True))
    if "refunded_at" not in sale_cols:
        op.add_column("sales", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for col in ("refunded_at", "stripe_refund_id", "credit_note_number", "original_sale_id", "kind"):
        op.drop_column("sales", col)
    op.drop_table("return_receipts")
