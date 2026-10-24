"""Instanz-Reservierung: instances.reserved_for_order_id.

Bei Auftragsfreigabe werden zu verbrauchende Komponenten-Instanzen für genau
diesen Auftrag reserviert (DB-id des Auftrags). Reservierte Instanzen sind für
andere Aufträge nicht mehr verbrauchbar.

Revision ID: 024
Revises: 023
Create Date: 2026-06-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c['name'] for c in inspect(bind).get_columns('instances')}
    if 'reserved_for_order_id' not in cols:
        op.add_column('instances', sa.Column('reserved_for_order_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_instances_reserved_for_order_id', 'instances', ['reserved_for_order_id'])
    # Normalisierung: passed nur bei abgeschlossenem Auftrag
    op.execute(
        "UPDATE instances SET qc_status='pending', released_at=NULL "
        "WHERE qc_status='passed' AND is_active=true "
        "AND order_id IN (SELECT id FROM orders WHERE status <> 'completed')"
    )


def downgrade() -> None:
    op.drop_index('ix_instances_reserved_for_order_id', table_name='instances')
    op.drop_column('instances', 'reserved_for_order_id')
