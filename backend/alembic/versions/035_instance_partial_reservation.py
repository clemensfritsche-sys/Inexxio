"""Mengengenaue Instanz-Reservierung ohne Teilung: instances.reservations + reserved_quantity.

Eine Charge wird nicht mehr in eine zweite Instanz (mit eigener Objektnummer) geteilt.
Stattdessen merkt sich die Instanz pro Auftrag eine Menge (``reservations``) und führt
die Summe denormalisiert (``reserved_quantity``) für die Verfügbarkeits-Aggregate.

Revision ID: 035
Revises: 034
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import inspect

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('instances')}
    if 'reservations' not in cols:
        op.add_column('instances', sa.Column('reservations', JSONB(), nullable=True))
    if 'reserved_quantity' not in cols:
        op.add_column('instances', sa.Column('reserved_quantity', sa.Integer(),
                                              server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('instances', 'reserved_quantity')
    op.drop_column('instances', 'reservations')
