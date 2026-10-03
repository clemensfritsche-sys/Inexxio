"""Add claims table (Reklamation / RMA)

Revision ID: 015
Revises: 014
Create Date: 2026-06-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, 'claims'):
        op.create_table(
            'claims',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
            sa.Column('direction', sa.String(length=20), nullable=False, server_default='internal'),
            sa.Column('instance_object_id', sa.BigInteger(), nullable=True),
            sa.Column('article_object_id', sa.BigInteger(), nullable=True),
            sa.Column('order_object_id', sa.BigInteger(), nullable=True),
            sa.Column('reason', sa.String(length=30), nullable=False, server_default='defect'),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('quantity', sa.Integer(), nullable=True),
            sa.Column('resolution', sa.String(length=20), nullable=False, server_default='none'),
            sa.Column('resolution_note', sa.Text(), nullable=True),
            sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
            sa.Column('reported_by_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('object_id'),
        )
        op.create_index(op.f('ix_claims_object_id'), 'claims', ['object_id'], unique=False)
        op.create_index(op.f('ix_claims_instance_object_id'), 'claims', ['instance_object_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'claims'):
        op.drop_index(op.f('ix_claims_instance_object_id'), table_name='claims')
        op.drop_index(op.f('ix_claims_object_id'), table_name='claims')
        op.drop_table('claims')
