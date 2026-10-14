"""Prozessschritt «Verschrotten»: Tabelle ``disposals`` (Abschluss-Marker).

Verschrotten ist die definierte Auflösung einer Abweichung: gewählte Instanzen werden
``disposition='scrapped'`` gesetzt; ein ``Disposal``-Datensatz markiert den Abschluss des
Schritts (analog ``movements`` – keine eigene Objektnummer).

Revision ID: 038
Revises: 037
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if insp.has_table('disposals'):
        return
    op.create_table(
        'disposals',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('step_id', sa.BigInteger(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('scrapped_by_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_disposals_order_id', 'disposals', ['order_id'])
    op.create_index('ix_disposals_step_id', 'disposals', ['step_id'])


def downgrade() -> None:
    op.drop_index('ix_disposals_step_id', table_name='disposals')
    op.drop_index('ix_disposals_order_id', table_name='disposals')
    op.drop_table('disposals')
