"""Lagerplatz als Instanz (F) + Standort-Pflicht gelockert.

* ``articles.is_location`` (BOOL) – markiert einen **Standort-Typ**: seine Instanzen sind
  Orte (``disposition='location'``), aus dem Bestand ausgeschlossen.
* ``instances.order_id`` wird **nullable** – eine Lagerplatz-Instanz hat keinen Auftrag.

Revision ID: 062
Revises: 061
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '062'
down_revision = '061'
branch_labels = None
depends_on = None


def _has_column(insp, table: str, name: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return name in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "articles" in insp.get_table_names() and not _has_column(insp, "articles", "is_location"):
        op.add_column("articles", sa.Column(
            "is_location", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if _has_column(insp, "instances", "order_id"):
        col = next(c for c in insp.get_columns("instances") if c["name"] == "order_id")
        if not col["nullable"]:
            op.alter_column("instances", "order_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if _has_column(insp, "instances", "order_id"):
        col = next(c for c in insp.get_columns("instances") if c["name"] == "order_id")
        if col["nullable"]:
            op.alter_column("instances", "order_id", existing_type=sa.BigInteger(), nullable=False)
    if _has_column(insp, "articles", "is_location"):
        op.drop_column("articles", "is_location")
