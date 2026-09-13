"""Bedarf-/Nachschub-Modell: Unter-Auftrag-Grund (reason) + Aufräumen.

Make-to-Order ist kein Sonderfall mehr (kein verketteter Produktionsauftrag, keine
Quellen-Übersteuerung). Stattdessen: EIN Unter-Auftrag-Mechanismus mit ``reason``
(``deviation`` = Abweichung | ``supply`` = Nachschub). WOHER die Stück kommen, leitet
sich aus der Auftragsgestalt ab (``services/subject.subject_kind``); ein Bedarf, der
nicht aus dem Bestand gedeckt ist, wird über einen Nachschub-Unter-Auftrag (reason=
'supply') produziert/beschafft und bei Abschluss an den Eltern gepinnt.

→ ``orders.reason`` neu; ``orders.subject_source`` und ``orders.fulfilled_by_order_id``
  (samt Index) entfernt.

Revision ID: 044
Revises: 043
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '044'
down_revision = '043'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, index: str) -> bool:
    return table in insp.get_table_names() and index in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_col(insp, "orders", "reason"):
        op.add_column("orders", sa.Column("reason", sa.String(length=12), nullable=True))
    if _has_index(insp, "orders", "ix_orders_fulfilled_by_order_id"):
        op.drop_index("ix_orders_fulfilled_by_order_id", table_name="orders")
    if _has_col(insp, "orders", "fulfilled_by_order_id"):
        op.drop_column("orders", "fulfilled_by_order_id")
    if _has_col(insp, "orders", "subject_source"):
        op.drop_column("orders", "subject_source")


def downgrade() -> None:
    op.add_column("orders", sa.Column("subject_source", sa.String(length=10), nullable=True))
    op.add_column("orders", sa.Column("fulfilled_by_order_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_orders_fulfilled_by_order_id", "orders", ["fulfilled_by_order_id"])
    op.drop_column("orders", "reason")
