"""Purchase-Modul: Prozessschritte am Artikel + Bestellungen (Purchase Orders)

Revision ID: 007
Revises: 006
Create Date: 2026-06-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── Neue Spalten auf bestehenden Tabellen ────────────────────────────────
    if 'landed_unit_cost' not in _columns(bind, 'articles'):
        op.add_column('articles', sa.Column('landed_unit_cost', sa.Numeric(12, 4), nullable=True))

    order_cols = _columns(bind, 'orders')
    if 'article_id' not in order_cols:
        op.add_column('orders', sa.Column('article_id', sa.BigInteger(), nullable=True))
        op.create_index(op.f('ix_orders_article_id'), 'orders', ['article_id'], unique=False)
    if 'quantity' not in order_cols:
        op.add_column('orders', sa.Column('quantity', sa.Integer(), nullable=True))
    if 'desired_delivery_date' not in order_cols:
        op.add_column('orders', sa.Column('desired_delivery_date', sa.Date(), nullable=True))

    # ── article_process_steps ────────────────────────────────────────────────
    if not _has_table(bind, 'article_process_steps'):
        op.create_table(
            'article_process_steps',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('article_id', sa.BigInteger(), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('step_type', sa.String(length=30), nullable=False, server_default='purchase'),
            sa.Column('mode', sa.String(length=20), nullable=False, server_default='supplier'),
            sa.Column('supplier_id', sa.BigInteger(), nullable=True),
            sa.Column('webshop_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_article_process_steps_article_id'),
                        'article_process_steps', ['article_id'], unique=False)

    # ── purchase_orders ──────────────────────────────────────────────────────
    if not _has_table(bind, 'purchase_orders'):
        op.create_table(
            'purchase_orders',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True),
            sa.Column('order_id', sa.BigInteger(), nullable=False),
            sa.Column('article_id', sa.BigInteger(), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('mode', sa.String(length=20), nullable=False, server_default='supplier'),
            sa.Column('supplier_id', sa.BigInteger(), nullable=True),
            sa.Column('webshop_url', sa.String(length=500), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='requested'),
            sa.Column('unit_price', sa.Numeric(12, 2), nullable=True),
            sa.Column('transport_cost', sa.Numeric(12, 2), nullable=True),
            sa.Column('transport_included', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('other_costs', sa.Numeric(12, 2), nullable=True),
            sa.Column('lead_time_days', sa.Integer(), nullable=True),
            sa.Column('payment_terms_days', sa.Integer(), nullable=True),
            sa.Column('desired_delivery_date', sa.Date(), nullable=True),
            sa.Column('tracking_number', sa.String(length=100), nullable=True),
            sa.Column('rejection_reason', sa.String(length=500), nullable=True),
            sa.Column('landed_unit_cost', sa.Numeric(12, 4), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('object_id'),
        )
        op.create_index(op.f('ix_purchase_orders_object_id'), 'purchase_orders', ['object_id'], unique=False)
        op.create_index(op.f('ix_purchase_orders_order_id'), 'purchase_orders', ['order_id'], unique=False)
        op.create_index(op.f('ix_purchase_orders_article_id'), 'purchase_orders', ['article_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'purchase_orders'):
        op.drop_index(op.f('ix_purchase_orders_article_id'), table_name='purchase_orders')
        op.drop_index(op.f('ix_purchase_orders_order_id'), table_name='purchase_orders')
        op.drop_index(op.f('ix_purchase_orders_object_id'), table_name='purchase_orders')
        op.drop_table('purchase_orders')
    if _has_table(bind, 'article_process_steps'):
        op.drop_index(op.f('ix_article_process_steps_article_id'), table_name='article_process_steps')
        op.drop_table('article_process_steps')
    order_cols = _columns(bind, 'orders')
    if 'desired_delivery_date' in order_cols:
        op.drop_column('orders', 'desired_delivery_date')
    if 'quantity' in order_cols:
        op.drop_column('orders', 'quantity')
    if 'article_id' in order_cols:
        op.drop_index(op.f('ix_orders_article_id'), table_name='orders')
        op.drop_column('orders', 'article_id')
    if 'landed_unit_cost' in _columns(bind, 'articles'):
        op.drop_column('articles', 'landed_unit_cost')
