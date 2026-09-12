"""Optionales Artikel-Feld: Lieferanten-Artikelnummer.

Revision ID: 023
Revises: 022
Create Date: 2026-06-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c['name'] for c in inspect(bind).get_columns('articles')}
    if 'supplier_article_number' not in cols:
        op.add_column('articles', sa.Column('supplier_article_number', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('articles', 'supplier_article_number')
