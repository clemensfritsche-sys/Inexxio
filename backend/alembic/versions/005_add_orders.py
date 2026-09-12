"""Add orders table (Auftrag)

Revision ID: 005
Revises: 004
Create Date: 2026-06-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'orders'):
        return

    op.create_table(
        'orders',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('object_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('object_id'),
    )
    op.create_index(op.f('ix_orders_object_id'), 'orders', ['object_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, 'orders'):
        return
    op.drop_index(op.f('ix_orders_object_id'), table_name='orders')
    op.drop_table('orders')
