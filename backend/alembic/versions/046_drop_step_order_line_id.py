"""Verkauf ist EIN Schritt, kein order_line_id nötig mehr.

Der Verkaufs-Schritt eines Mehrpositionen-Auftrags ist – wie jeder andere Schritttyp –
GENAU EINER; mehrere Belege (ein Artikel/Position je Beleg) teilen sich denselben
``step_id`` (``services/sale.py: instantiate_for_order``). Die in Migration 045 probeweise
eingeführte Bindung eines Schritts an EINE Position (``order_line_id``, für ein zwischen-
zeitliches Mehr-Schritt-Modell) entfällt damit wieder.

Revision ID: 046
Revises: 045
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '046'
down_revision = '045'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def _has_index(insp, table: str, index: str) -> bool:
    return table in insp.get_table_names() and index in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if _has_index(insp, "article_process_steps", "ix_article_process_steps_order_line_id"):
        op.drop_index("ix_article_process_steps_order_line_id", table_name="article_process_steps")
    if _has_col(insp, "article_process_steps", "order_line_id"):
        op.drop_column("article_process_steps", "order_line_id")


def downgrade() -> None:
    op.add_column("article_process_steps", sa.Column("order_line_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_article_process_steps_order_line_id", "article_process_steps", ["order_line_id"])
