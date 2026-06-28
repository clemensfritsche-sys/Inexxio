"""Abweichung als Auftrag: orders.parent_order_id + abort_into_id.

Eine Abweichung (vereinheitlicht Reklamation/Fehler/Nacharbeit/Abbruch-Folgeauftrag) ist
ein Unter-Auftrag mit ``parent_order_id``. ``abort_into_id`` verlinkt den beim Abbruch
erzwungenen Folgeauftrag (Original wird erst inaktiv, wenn dieser freigegeben ist).

Revision ID: 036
Revises: 035
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('orders')}
    if 'parent_order_id' not in cols:
        op.add_column('orders', sa.Column('parent_order_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_orders_parent_order_id', 'orders', ['parent_order_id'])
    if 'abort_into_id' not in cols:
        op.add_column('orders', sa.Column('abort_into_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_orders_abort_into_id', 'orders', ['abort_into_id'])


def downgrade() -> None:
    op.drop_index('ix_orders_abort_into_id', table_name='orders')
    op.drop_index('ix_orders_parent_order_id', table_name='orders')
    op.drop_column('orders', 'abort_into_id')
    op.drop_column('orders', 'parent_order_id')
