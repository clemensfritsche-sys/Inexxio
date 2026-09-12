"""Beschaffung verschlanken: ordered_at, weniger Spalten, Status-Migration

- purchase_orders: ordered_at ergänzen; unit_price & desired_delivery_date entfernen.
- article_process_steps: position entfernen.
- Status approved/confirmed → ordered.

Revision ID: 010
Revises: 009
Create Date: 2026-06-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if 'ordered_at' not in _columns(bind, 'purchase_orders'):
        op.add_column('purchase_orders', sa.Column('ordered_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE purchase_orders SET status='ordered' WHERE status IN ('approved','confirmed')")
    op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS unit_price")
    op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS desired_delivery_date")
    op.execute("ALTER TABLE article_process_steps DROP COLUMN IF EXISTS position")


def downgrade() -> None:
    bind = op.get_bind()
    if 'position' not in _columns(bind, 'article_process_steps'):
        op.add_column('article_process_steps', sa.Column('position', sa.Integer(), server_default='1', nullable=False))
    if 'desired_delivery_date' not in _columns(bind, 'purchase_orders'):
        op.add_column('purchase_orders', sa.Column('desired_delivery_date', sa.Date(), nullable=True))
    if 'unit_price' not in _columns(bind, 'purchase_orders'):
        op.add_column('purchase_orders', sa.Column('unit_price', sa.Numeric(12, 2), nullable=True))
    op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS ordered_at")
