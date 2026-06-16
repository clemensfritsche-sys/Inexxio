"""Serialisierung (instances) + Eingangskontrolle (inspections) + Schritt-Reihenfolge

Revision ID: 011
Revises: 010
Create Date: 2026-06-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    aps = _columns(bind, 'article_process_steps')
    if 'position' not in aps:
        op.add_column('article_process_steps', sa.Column('position', sa.Integer(), server_default='1', nullable=False))
    if 'sample_percent' not in aps:
        op.add_column('article_process_steps', sa.Column('sample_percent', sa.Integer(), nullable=True))

    if not _has_table(bind, 'instances'):
        op.create_table(
            'instances',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True),
            sa.Column('article_id', sa.BigInteger(), nullable=False),
            sa.Column('order_id', sa.BigInteger(), nullable=False),
            sa.Column('kind', sa.String(length=10), nullable=False, server_default='unit'),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('serial_number', sa.String(length=60), nullable=True),
            sa.Column('qc_status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('object_id'),
        )
        op.create_index(op.f('ix_instances_object_id'), 'instances', ['object_id'], unique=False)
        op.create_index(op.f('ix_instances_article_id'), 'instances', ['article_id'], unique=False)
        op.create_index(op.f('ix_instances_order_id'), 'instances', ['order_id'], unique=False)

    if not _has_table(bind, 'inspections'):
        op.create_table(
            'inspections',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('order_id', sa.BigInteger(), nullable=False),
            sa.Column('article_id', sa.BigInteger(), nullable=False),
            sa.Column('result', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('checked_count', sa.Integer(), nullable=True),
            sa.Column('note', sa.String(length=500), nullable=True),
            sa.Column('inspector_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_inspections_order_id'), 'inspections', ['order_id'], unique=False)
        op.create_index(op.f('ix_inspections_article_id'), 'inspections', ['article_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'inspections'):
        op.drop_table('inspections')
    if _has_table(bind, 'instances'):
        op.drop_table('instances')
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS sample_percent")
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS position")
