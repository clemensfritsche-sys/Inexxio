"""Datenerfassung je Instanz (inspections.samples), Lagerplatz-Bemerkung,
Artikelnamen-Katalog in den Systemkonfigurationen

Revision ID: 014
Revises: 013
Create Date: 2026-06-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if 'samples' not in _columns(bind, 'inspections'):
        op.add_column('inspections', sa.Column('samples', JSONB, nullable=True))
    if 'note' not in _columns(bind, 'storage_locations'):
        op.add_column('storage_locations', sa.Column('note', sa.String(length=500), nullable=True))
    if 'article_names' not in _columns(bind, 'company_settings'):
        op.add_column('company_settings', sa.Column('article_names', JSONB, nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE company_settings DROP COLUMN IF EXISTS article_names")
    op.execute("ALTER TABLE storage_locations DROP COLUMN IF EXISTS note")
    op.execute("ALTER TABLE inspections DROP COLUMN IF EXISTS samples")
