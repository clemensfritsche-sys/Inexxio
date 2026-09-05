"""Optionale Artikel-Stammdaten + Durchlaufzeit (orders.released_at/completed_at) +
Mehr-Operationen-Routing (step_id auf den Fachtabellen).

Revision ID: 019
Revises: 018
Create Date: 2026-06-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def _add(bind, table: str, column: sa.Column) -> None:
    if _has_table(bind, table) and column.name not in _columns(bind, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()

    # Optionale Artikel-Stammdaten (dynamische Feldliste)
    _add(bind, 'articles', sa.Column('material', sa.String(length=255), nullable=True))
    _add(bind, 'articles', sa.Column('cad_url', sa.String(length=500), nullable=True))
    _add(bind, 'articles', sa.Column('surface', sa.String(length=255), nullable=True))
    _add(bind, 'articles', sa.Column('min_order_qty', sa.Numeric(12, 3), nullable=True))
    _add(bind, 'articles', sa.Column('safety_stock', sa.Numeric(12, 3), nullable=True))

    # Durchlaufzeit (Freigabe → Abschluss)
    _add(bind, 'orders', sa.Column('released_at', sa.DateTime(timezone=True), nullable=True))
    _add(bind, 'orders', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))

    # Mehr-Operationen-Routing: Fachzeilen an ihre Schritt-Definition binden
    for table in ('purchase_orders', 'inspections', 'movements', 'resource_usages'):
        _add(bind, table, sa.Column('step_id', sa.BigInteger(), nullable=True))
        if _has_table(bind, table) and 'step_id' in _columns(bind, table):
            op.create_index(op.f(f'ix_{table}_step_id'), table, ['step_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in ('purchase_orders', 'inspections', 'movements', 'resource_usages'):
        if _has_table(bind, table):
            op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS step_id")
    if _has_table(bind, 'orders'):
        op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS released_at")
        op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS completed_at")
    if _has_table(bind, 'articles'):
        for col in ('material', 'cad_url', 'surface', 'min_order_qty', 'safety_stock'):
            op.execute(f"ALTER TABLE articles DROP COLUMN IF EXISTS {col}")
