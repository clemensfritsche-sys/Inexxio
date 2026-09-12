"""Beschaffungsquelle an der Artikel-Spezifikation (statt am Beschaffungs-Prozessschritt).

WO ein Artikel beschafft wird, gehört zur Produktspezifikation – nicht in jeden einzelnen
``purchase``-Prozessschritt. Der Schritt bleibt der Auslöser und **erbt** diese Quelle als
Default (pro Fall überschreibbar). Neue Artikel-Spalten:
    procurement_mode      (supplier | webshop, Default 'supplier')
    default_supplier_id   (UserProfile, Rolle 'supplier')
    default_webshop_url   (Beschaffungs-Link)

Revision ID: 056
Revises: 055
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '056'
down_revision = '055'
branch_labels = None
depends_on = None

_COLS = (
    ("procurement_mode", sa.Column("procurement_mode", sa.String(20), nullable=False, server_default="supplier")),
    ("default_supplier_id", sa.Column("default_supplier_id", sa.BigInteger(), nullable=True)),
    ("default_webshop_url", sa.Column("default_webshop_url", sa.String(500), nullable=True)),
)


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "articles" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("articles")}
    for name, col in _COLS:
        if name not in have:
            op.add_column("articles", col)


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "articles" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("articles")}
    for name, _col in reversed(_COLS):
        if name in have:
            op.drop_column("articles", name)
