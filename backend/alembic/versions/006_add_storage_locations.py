"""Add storage_locations table (Lagerplatz) + google_maps_api_key setting

Revision ID: 006
Revises: 005
Create Date: 2026-06-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if 'google_maps_api_key' not in _columns(bind, 'company_settings'):
        op.add_column('company_settings', sa.Column('google_maps_api_key', sa.String(255), nullable=True))

    if not _has_table(bind, 'storage_locations'):
        op.create_table(
            'storage_locations',
            sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('code', sa.String(length=100), nullable=True),
            sa.Column('location_type', sa.String(length=30), nullable=True),
            sa.Column('max_load_kg', sa.Numeric(precision=12, scale=3), nullable=True),
            sa.Column('width_mm', sa.Integer(), nullable=True),
            sa.Column('depth_mm', sa.Integer(), nullable=True),
            sa.Column('height_mm', sa.Integer(), nullable=True),
            sa.Column('is_dry', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_tempered', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_hazmat', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
            sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
            sa.Column('address_street', sa.String(length=255), nullable=True),
            sa.Column('address_zip', sa.String(length=20), nullable=True),
            sa.Column('address_city', sa.String(length=100), nullable=True),
            sa.Column('address_country', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('object_id'),
        )
        op.create_index(op.f('ix_storage_locations_object_id'), 'storage_locations', ['object_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'storage_locations'):
        op.drop_index(op.f('ix_storage_locations_object_id'), table_name='storage_locations')
        op.drop_table('storage_locations')
    if 'google_maps_api_key' in _columns(bind, 'company_settings'):
        op.drop_column('company_settings', 'google_maps_api_key')
