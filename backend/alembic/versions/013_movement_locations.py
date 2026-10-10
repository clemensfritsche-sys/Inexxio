"""Bewegung: Standorte der Instanzen (location_type/id), movements-Tabelle,
Bewegungs-Vorgabeziel am Prozessschritt, Standard-Wareneingang in den Settings

Revision ID: 013
Revises: 012
Create Date: 2026-06-17
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    inst = _columns(bind, 'instances')
    if 'location_type' not in inst:
        op.add_column('instances', sa.Column('location_type', sa.String(length=20), nullable=True))
    if 'location_id' not in inst:
        op.add_column('instances', sa.Column('location_id', sa.BigInteger(), nullable=True))

    aps = _columns(bind, 'article_process_steps')
    if 'target_location_type' not in aps:
        op.add_column('article_process_steps', sa.Column('target_location_type', sa.String(length=20), nullable=True))
    if 'target_location_id' not in aps:
        op.add_column('article_process_steps', sa.Column('target_location_id', sa.BigInteger(), nullable=True))

    if 'default_receiving_location_id' not in _columns(bind, 'company_settings'):
        op.add_column('company_settings', sa.Column('default_receiving_location_id', sa.BigInteger(), nullable=True))

    if not _has_table(bind, 'movements'):
        op.create_table(
            'movements',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('order_id', sa.BigInteger(), nullable=False),
            sa.Column('note', sa.String(length=500), nullable=True),
            sa.Column('moved_by_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_movements_order_id'), 'movements', ['order_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'movements'):
        op.drop_table('movements')
    op.execute("ALTER TABLE company_settings DROP COLUMN IF EXISTS default_receiving_location_id")
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS target_location_id")
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS target_location_type")
    op.execute("ALTER TABLE instances DROP COLUMN IF EXISTS location_id")
    op.execute("ALTER TABLE instances DROP COLUMN IF EXISTS location_type")
