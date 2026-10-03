"""Haltbarkeit/Ablauf entfernen (E) – die Instanz-Ablauf-Funktion wird gestrichen.

Das MHD-getriebene Ausbuchen von Instanzen (``instances.expires_at`` + ``articles.shelf_life_days``
+ der Sweep in ``services/expiry.py``) wird komplett entfernt. Der Meldebestand (``safety_stock`` +
``reorder_target``) bleibt bestehen – nur die Haltbarkeits-/Ablauf-Achse fällt weg.

Entfernte Spalten:
    instances.expires_at      TIMESTAMPTZ   – Ablaufdatum (wurde bei Freigabe gesetzt)
    articles.shelf_life_days  BIGINT        – Haltbarkeit in Tagen

Revision ID: 061
Revises: 060
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '061'
down_revision = '060'
branch_labels = None
depends_on = None


def _drop(table: str, names) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    for name in names:
        if name in have:
            op.drop_column(table, name)


def _add(table: str, cols) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    for name, col in cols:
        if name not in have:
            op.add_column(table, col)


def upgrade() -> None:
    _drop("instances", ("expires_at",))
    _drop("articles", ("shelf_life_days",))


def downgrade() -> None:
    _add("articles", (("shelf_life_days", sa.Column("shelf_life_days", sa.BigInteger(), nullable=True)),))
    _add("instances", (("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)),))
