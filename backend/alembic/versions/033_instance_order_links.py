"""Unveränderliche Instanz↔Auftrag-Verweise (Auftrags-Historie einer Instanz).

Die Historie „welche Aufträge haben diese Instanz verarbeitet" darf nicht von
veränderlichen Zeigern abhängen (``subject_of_order_id`` wandert/wird gelöst). Jede
Verarbeitung wird bei der Freigabe einmal dauerhaft in ``instance_order_links`` festgehalten.

Revision ID: 033
Revises: 032
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if 'instance_order_links' in insp.get_table_names():
        return
    op.create_table(
        'instance_order_links',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('instance_object_id', sa.BigInteger(), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_instance_order_links_instance_object_id', 'instance_order_links', ['instance_object_id'])
    op.create_index('ix_instance_order_links_order_id', 'instance_order_links', ['order_id'])


def downgrade() -> None:
    op.drop_table('instance_order_links')
