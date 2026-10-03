"""Datenerfassung: capture_fields (Maske) + inspection values

Revision ID: 012
Revises: 011
Create Date: 2026-06-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if 'capture_fields' not in _columns(bind, 'article_process_steps'):
        op.add_column('article_process_steps', sa.Column('capture_fields', JSONB, nullable=True))
    if 'values' not in _columns(bind, 'inspections'):
        op.add_column('inspections', sa.Column('values', JSONB, nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE inspections DROP COLUMN IF EXISTS values")
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS capture_fields")
