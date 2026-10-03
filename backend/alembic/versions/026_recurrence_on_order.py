"""Wiederkehrende Aufträge direkt am Auftrag (kein eigenes Objekt mehr).

Recurrence-Konfiguration wandert auf ``orders``; die Tabelle ``recurring_orders``
wird entfernt. Ein abgeschlossener wiederkehrender Auftrag erzeugt den nächsten
(Entwurf) automatisch – siehe ``services/process.recompute_completion``.

Revision ID: 026
Revises: 025
Create Date: 2026-06-24
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {
        'recurrence_active': sa.Column('recurrence_active', sa.Boolean(), nullable=False, server_default='false'),
        'recurrence_interval_days': sa.Column('recurrence_interval_days', sa.Integer(), nullable=True),
        'recurrence_lead_time_days': sa.Column('recurrence_lead_time_days', sa.Integer(), nullable=False, server_default='0'),
        'recurrence_anchor': sa.Column('recurrence_anchor', sa.Date(), nullable=True),
        'recurring_parent_id': sa.Column('recurring_parent_id', sa.BigInteger(), nullable=True),
    }
    for name, col in cols.items():
        if not _has_col(insp, 'orders', name):
            op.add_column('orders', col)
    if 'recurring_orders' in insp.get_table_names():
        op.drop_table('recurring_orders')


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for name in ('recurring_parent_id', 'recurrence_anchor', 'recurrence_lead_time_days',
                 'recurrence_interval_days', 'recurrence_active'):
        if _has_col(insp, 'orders', name):
            op.drop_column('orders', name)
    # recurring_orders wird im downgrade NICHT wiederhergestellt (Datenverlust vermeiden,
    # Tabelle war neu und leer).
