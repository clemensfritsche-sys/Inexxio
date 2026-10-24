"""Prozessschritt «Ressource»: resource_usages + instances.released_at (FIFO) +
article_process_steps.resource_lines

Revision ID: 018
Revises: 017
Create Date: 2026-06-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, 'instances') and 'released_at' not in _columns(bind, 'instances'):
        op.add_column('instances', sa.Column('released_at', sa.DateTime(timezone=True), nullable=True))

    if _has_table(bind, 'article_process_steps') and 'resource_lines' not in _columns(bind, 'article_process_steps'):
        op.add_column('article_process_steps', sa.Column('resource_lines', JSONB(), nullable=True))

    if not _has_table(bind, 'resource_usages'):
        op.create_table(
            'resource_usages',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('order_id', sa.BigInteger(), nullable=False),
            sa.Column('used_by_id', sa.BigInteger(), nullable=True),
            sa.Column('note', sa.String(length=500), nullable=True),
            sa.Column('details', JSONB(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_resource_usages_order_id'), 'resource_usages', ['order_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'resource_usages'):
        op.drop_table('resource_usages')
    if _has_table(bind, 'article_process_steps'):
        op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS resource_lines")
    if _has_table(bind, 'instances'):
        op.execute("ALTER TABLE instances DROP COLUMN IF EXISTS released_at")
