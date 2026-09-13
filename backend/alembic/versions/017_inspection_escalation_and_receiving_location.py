"""Datenerfassung 100%-Hochstufung (inspections.escalated) + Lieferadresse je
Beschaffungsschritt (purchase_orders.receiving_location_id)

Revision ID: 017
Revises: 016
Create Date: 2026-06-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'inspections') and 'escalated' not in _columns(bind, 'inspections'):
        op.add_column('inspections', sa.Column(
            'escalated', sa.Boolean(), server_default=sa.false(), nullable=False))
    if _has_table(bind, 'purchase_orders') and 'receiving_location_id' not in _columns(bind, 'purchase_orders'):
        op.add_column('purchase_orders', sa.Column(
            'receiving_location_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'purchase_orders'):
        op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS receiving_location_id")
    if _has_table(bind, 'inspections'):
        op.execute("ALTER TABLE inspections DROP COLUMN IF EXISTS escalated")
