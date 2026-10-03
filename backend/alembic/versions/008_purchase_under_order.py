"""Bestellung läuft unter der Auftragsnummer: purchase_orders.object_id entfernen

Revision ID: 008
Revises: 007
Create Date: 2026-06-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if 'object_id' in _columns(bind, 'purchase_orders'):
        # Index/Unique-Constraint hängen an der Spalte und fallen mit ihr weg.
        op.execute("DROP INDEX IF EXISTS ix_purchase_orders_object_id")
        op.execute("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS object_id")


def downgrade() -> None:
    bind = op.get_bind()
    if 'object_id' not in _columns(bind, 'purchase_orders'):
        op.add_column('purchase_orders', sa.Column('object_id', sa.BigInteger(), nullable=True))
        op.create_index(op.f('ix_purchase_orders_object_id'), 'purchase_orders', ['object_id'], unique=False)
