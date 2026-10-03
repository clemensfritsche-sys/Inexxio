"""Add articles table (Artikel-Stammdaten)

Revision ID: 004
Revises: 003
Create Date: 2026-06-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'articles'):
        return

    op.create_table(
        'articles',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('object_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('unit', sa.String(length=10), nullable=False),
        sa.Column('serialization', sa.String(length=20), nullable=False),
        sa.Column('size', sa.String(length=100), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('object_id'),
    )
    op.create_index(op.f('ix_articles_object_id'), 'articles', ['object_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, 'articles'):
        return
    op.drop_index(op.f('ix_articles_object_id'), table_name='articles')
    op.drop_table('articles')
