"""Datenerfassung an einem Mehrpositionen-Auftrag: article_id nullable.

Ein Mehrpositionen-Auftrag (``order.article_id IS NULL``) legt EINE Datenerfassung an,
die artikelübergreifend aus ALLEN Subjekt-Instanzen des Auftrags eine Stichprobe zieht
(``services/inspection.py``) – anders als Verkauf/Beschaffung braucht sie keine eigene
Fachzeile je Artikel. ``inspections.article_id`` muss dafür NULL sein dürfen.

Revision ID: 047
Revises: 046
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '047'
down_revision = '046'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c["name"]: c for c in insp.get_columns("inspections")} if "inspections" in insp.get_table_names() else {}
    if cols.get("article_id", {}).get("nullable") is False:
        op.alter_column("inspections", "article_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column("inspections", "article_id", existing_type=sa.BigInteger(), nullable=False)
