"""Add serialization_type to items

Revision ID: 008
Revises: 007
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'items',
        sa.Column('serialization_type', sa.String(20), nullable=False, server_default='none'),
    )


def downgrade():
    op.drop_column('items', 'serialization_type')
