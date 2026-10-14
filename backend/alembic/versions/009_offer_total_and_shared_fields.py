"""Offerte als Bestellsumme + freigegebene Stammdaten

- purchase_orders: order_total ergänzen; transport_cost, transport_included,
  other_costs, rejection_reason entfernen.
- article_process_steps: shared_fields (JSONB) ergänzen.

Revision ID: 009
Revises: 008
Create Date: 2026-06-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    po = _columns(bind, 'purchase_orders')
    if 'order_total' not in po:
        op.add_column('purchase_orders', sa.Column('order_total', sa.Numeric(12, 2), nullable=True))
    for col in ('transport_cost', 'transport_included', 'other_costs', 'rejection_reason'):
        op.execute(f"ALTER TABLE purchase_orders DROP COLUMN IF EXISTS {col}")

    if 'shared_fields' not in _columns(bind, 'article_process_steps'):
        op.add_column('article_process_steps', sa.Column('shared_fields', JSONB, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS shared_fields")
    po = _columns(bind, 'purchase_orders')
    if 'rejection_reason' not in po:
        op.add_column('purchase_orders', sa.Column('rejection_reason', sa.String(500), nullable=True))
    if 'other_costs' not in po:
        op.add_column('purchase_orders', sa.Column('other_costs', sa.Numeric(12, 2), nullable=True))
    if 'transport_included' not in po:
        op.add_column('purchase_orders', sa.Column('transport_included', sa.Boolean(), server_default=sa.false(), nullable=False))
    if 'transport_cost' not in po:
        op.add_column('purchase_orders', sa.Column('transport_cost', sa.Numeric(12, 2), nullable=True))
    op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS order_total")
