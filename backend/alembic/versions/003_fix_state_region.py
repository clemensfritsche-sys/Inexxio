"""Fix state_region column: handle all possible DB states from migration 002

Revision ID: 003
Revises: 002
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, 'user_profiles')

    if 'state_canton' in cols and 'state_region' not in cols:
        op.alter_column('user_profiles', 'state_canton', new_column_name='state_region')
    elif 'state_canton' in cols and 'state_region' in cols:
        op.drop_column('user_profiles', 'state_canton')
    elif 'state_region' not in cols:
        op.add_column('user_profiles', sa.Column('state_region', sa.String(100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, 'user_profiles')

    if 'state_region' in cols and 'state_canton' not in cols:
        op.alter_column('user_profiles', 'state_region', new_column_name='state_canton')
