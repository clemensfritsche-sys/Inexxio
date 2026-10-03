"""Mehrpositionen-Aufträge (order_lines) + Verkaufs-Herkunft/Zahlungsart.

ERP soll einen personal-erfassten Verkauf über MEHRERE Artikel (eine Sendung) genauso
abbilden können wie der Shop-Warenkorb – ohne den bestehenden Einzel-Artikel-Auftrag
(``orders.article_id``/``quantity``) anzutasten. Neue Tabelle ``order_lines`` bündelt
Artikel+Menge für einen Mehrpositionen-Auftrag (``orders.article_id IS NULL``); eine
Herstell-/Beschaffungs-Position bleibt wie im Shop ein **eigener** Auftrag.

``article_process_steps.order_line_id`` bindet einen ``sale``-Schritt an genau eine
Position (Mehrpositionen-Fall). ``sales.mode`` hält fest, ob ein Verkauf über den Shop
(Stripe) oder direkt im ERP erfasst wurde; ``payment_method``/``payment_reference``
erfassen den manuellen Zahlungseingang (Rechnung/Bar/Twint – kein Kartenterminal nötig).

Revision ID: 045
Revises: 044
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '045'
down_revision = '044'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "order_lines" not in insp.get_table_names():
        op.create_table(
            "order_lines",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("article_id", sa.BigInteger(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )
        op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])
        op.create_index("ix_order_lines_article_id", "order_lines", ["article_id"])

    if not _has_col(insp, "article_process_steps", "order_line_id"):
        op.add_column("article_process_steps",
                      sa.Column("order_line_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_article_process_steps_order_line_id", "article_process_steps",
                        ["order_line_id"])

    if not _has_col(insp, "sales", "mode"):
        op.add_column("sales", sa.Column("mode", sa.String(length=10), nullable=True))
    if not _has_col(insp, "sales", "payment_method"):
        op.add_column("sales", sa.Column("payment_method", sa.String(length=16), nullable=True))
    if not _has_col(insp, "sales", "payment_reference"):
        op.add_column("sales", sa.Column("payment_reference", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("sales", "payment_reference")
    op.drop_column("sales", "payment_method")
    op.drop_column("sales", "mode")
    op.drop_index("ix_article_process_steps_order_line_id", table_name="article_process_steps")
    op.drop_column("article_process_steps", "order_line_id")
    op.drop_index("ix_order_lines_article_id", table_name="order_lines")
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")
