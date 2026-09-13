"""Make-to-Order: Verknüpfung Verkaufsauftrag → Produktionsauftrag.

Ein Shop-**Verkaufsauftrag erzeugt NIE selbst Instanzen** (das darf nur der Artikel-Prozess).
Bei «auf Bestellung» (make) entsteht bei der Zahlung ein separater **Produktionsauftrag**
(fährt den Artikel-Prozess, erzeugt die Instanzen). Der Verkaufsauftrag trägt
``fulfilled_by_order_id`` = Objektnummer dieser Produktion und wird **freigegeben/erfüllt
(FIFO-Zuordnung + Versand), sobald die Produktion abgeschlossen ist**.

Revision ID: 043
Revises: 042
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '043'
down_revision = '042'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_col(insp, "orders", "fulfilled_by_order_id"):
        op.add_column("orders", sa.Column("fulfilled_by_order_id", sa.BigInteger(), nullable=True))
        op.create_index("ix_orders_fulfilled_by_order_id", "orders", ["fulfilled_by_order_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_fulfilled_by_order_id", table_name="orders")
    op.drop_column("orders", "fulfilled_by_order_id")
