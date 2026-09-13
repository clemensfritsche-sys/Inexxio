"""Domain-Event-Strom (transaktionaler Outbox) – Tabelle ``events``.

Append-only Ereignisstrom für KI-/Automatisierungs-Anbindung und Analytik.

Revision ID: 022
Revises: 021
Create Date: 2026-06-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if inspect(bind).has_table('events'):
        return
    op.create_table(
        'events',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('object_id', sa.BigInteger(), nullable=True),
        sa.Column('object_type', sa.String(length=30), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('payload', JSONB(), nullable=True),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_events_object_id'), 'events', ['object_id'], unique=False)
    op.create_index(op.f('ix_events_object_type'), 'events', ['object_type'], unique=False)
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'], unique=False)
    op.create_index(op.f('ix_events_created_at'), 'events', ['created_at'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if inspect(bind).has_table('events'):
        op.drop_table('events')
