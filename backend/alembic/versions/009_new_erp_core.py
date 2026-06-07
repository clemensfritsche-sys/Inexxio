"""New ERP core: ProzessSchritt, Auftrag, Objekt

Revision ID: 009
Revises: 008
Create Date: 2026-06-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prozess_schritte',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('beschreibung', sa.Text(), nullable=False),
        sa.Column('ressourcen', postgresql.JSONB(), nullable=True),
        sa.Column('daten_felder', postgresql.JSONB(), nullable=True),
        sa.Column('ergebnis_optionen', postgresql.JSONB(), nullable=True),
        sa.Column('aktion', postgresql.JSONB(), nullable=True),
        sa.Column('onshape_link', sa.String(500), nullable=True),
        sa.Column('dokument_link', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_prozess_schritte_item_id', 'prozess_schritte', ['item_id'])

    op.create_table(
        'auftraege',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('item_id', sa.BigInteger(), nullable=False),
        sa.Column('menge', sa.Numeric(15, 4), nullable=False, server_default='1'),
        sa.Column('datum_faellig', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='OFFEN'),
        sa.Column('notiz', sa.Text(), nullable=True),
        sa.Column('wiederkehrend', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('intervall_typ', sa.String(20), nullable=True),
        sa.Column('intervall_wert', sa.String(100), nullable=True),
        sa.Column('naechste_faelligkeit', sa.Date(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['id'], ['objects.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_auftraege_item_id', 'auftraege', ['item_id'])
    op.create_index('ix_auftraege_status', 'auftraege', ['status'])

    op.create_table(
        'objekte',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('item_id', sa.BigInteger(), nullable=False),
        sa.Column('auftrag_id', sa.BigInteger(), nullable=True),
        sa.Column('typ', sa.String(10), nullable=False),
        sa.Column('batch_menge', sa.Numeric(15, 4), nullable=True),
        sa.Column('batch_verbleibend', sa.Numeric(15, 4), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='VERFUEGBAR'),
        sa.Column('lagerort', sa.String(200), nullable=True),
        sa.Column('gueltig_bis', sa.Date(), nullable=True),
        sa.Column('schritt_protokoll', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['id'], ['objects.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['auftrag_id'], ['auftraege.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_objekte_item_id', 'objekte', ['item_id'])
    op.create_index('ix_objekte_status', 'objekte', ['status'])


def downgrade():
    op.drop_table('objekte')
    op.drop_table('auftraege')
    op.drop_table('prozess_schritte')
