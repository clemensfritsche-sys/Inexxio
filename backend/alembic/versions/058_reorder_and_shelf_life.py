"""Meldebestand / Auto-Nachbestellung + Haltbarkeit (E).

«Nicht die Zeit soll bestellen, sondern der Bestand»: fällt der freie Bestand unter den
Meldebestand (``articles.safety_stock``), legt das System einen Nachschub-Auftrag an (bis
``reorder_target``). Ablaufdatum (``articles.shelf_life_days`` → ``instances.expires_at``)
bucht abgelaufene Teile aus und füttert damit denselben Nachbestell-Auslöser.

Neue Spalten:
    articles.reorder_target   NUMERIC(12,3)   – Zielbestand nach Nachbestellung (optional)
    articles.shelf_life_days  BIGINT          – Haltbarkeit in Tagen (optional)
    instances.expires_at      TIMESTAMPTZ     – Ablaufdatum (bei Freigabe gesetzt)

Revision ID: 058
Revises: 057
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '058'
down_revision = '057'
branch_labels = None
depends_on = None

_ARTICLE_COLS = (
    ("reorder_target", sa.Column("reorder_target", sa.Numeric(12, 3), nullable=True)),
    ("shelf_life_days", sa.Column("shelf_life_days", sa.BigInteger(), nullable=True)),
)


def _add(table: str, cols) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    for name, col in cols:
        if name not in have:
            op.add_column(table, col)


def _drop(table: str, names) -> None:
    insp = inspect(op.get_bind())
    if table not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns(table)}
    for name in names:
        if name in have:
            op.drop_column(table, name)


def upgrade() -> None:
    _add("articles", _ARTICLE_COLS)
    _add("instances", (("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)),))


def downgrade() -> None:
    _drop("instances", ("expires_at",))
    _drop("articles", ("reorder_target", "shelf_life_days"))
