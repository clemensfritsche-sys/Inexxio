"""Unternehmen als nummerierter ERP-Datensatz: company_settings.object_id.

Das Unternehmen (Singleton) bekommt eine universelle Objektnummer und wird damit
ein vollwertiger ERP-Datensatz («Unternehmen» im Feed, vom Admin pflegbar). Die
Nummer wird lazy bei der ersten Abfrage vergeben (services/admin.get_or_create_settings).

Revision ID: 034
Revises: 033
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('company_settings')}
    if 'object_id' not in cols:
        op.add_column('company_settings', sa.Column('object_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_company_settings_object_id', 'company_settings', ['object_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_company_settings_object_id', table_name='company_settings')
    op.drop_column('company_settings', 'object_id')
